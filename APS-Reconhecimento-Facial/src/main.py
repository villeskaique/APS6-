from threading import Lock
from pathlib import Path
import cv2
import threading
import api
import uvicorn
from camera_compartilhada import atualizar_frame
from reconhecimento import reconhecer_imagem, reconhecimento_lock
from estado import atualizar_estado

# Dados exibidos na interface e controle das threads
estado_interface_lock = Lock()
reconhecimento_lock = Lock()
LIMITE_DISTANCIA = 0.55
nome_pessoa = ""
score = 0
nivel_acesso = 0
reconhecimento_em_andamento = False

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "database"


def atualizar_interface(nome="", distancia=0, nivel=0):
    global nome_pessoa, score, nivel_acesso

    # Impede que duas threads alterem os dados ao mesmo tempo
    with estado_interface_lock:
        nome_pessoa = nome
        score = distancia
        nivel_acesso = nivel


def reconhecer_rosto(frame):
    global reconhecimento_em_andamento

    try:
        resultado = reconhecer_imagem(frame)

        if resultado["autenticado"]:
            # Atualiza as informações mostradas na câmera
            atualizar_interface(
                resultado["usuario"],
                resultado["distancia"],
                resultado["nivel_acesso"]
            )

            # Compartilha o resultado com os demais módulos
            atualizar_estado(
                autenticado=True,
                id_usuario=resultado["id_usuario"],
                usuario=resultado["usuario"],
                nivel_acesso=resultado["nivel_acesso"],
                distancia=resultado["distancia"]
            )

            print("Pessoa encontrada:", resultado["usuario"])
            print("Distância:", round(resultado["distancia"], 3))
            print("Nível de acesso:", resultado["nivel_acesso"])

        else:
            atualizar_interface()
            atualizar_estado()
            print(resultado["mensagem"])

    except Exception as erro:
        atualizar_interface()
        atualizar_estado()
        print(f"Erro no reconhecimento: {erro}")

    finally:
        # Libera uma nova tentativa de reconhecimento
        with reconhecimento_lock:
            reconhecimento_em_andamento = False


def draw_rounded_retangle(
    img, top_left, bottom_right, color,
    radius=10, thickness=-1
):
    # Coordenadas dos cantos do retângulo
    x1, y1 = top_left
    x2, y2 = bottom_right

    # Desenha as partes retas
    cv2.rectangle(
        img, (x1 + radius, y1),
        (x2 - radius, y2), color, thickness
    )
    cv2.rectangle(
        img, (x1, y1 + radius),
        (x2, y2 - radius), color, thickness
    )

    # Completa os cantos arredondados com elipses
    cv2.ellipse(
        img, (x1 + radius, y1 + radius),
        (radius, radius), 180, 0, 90, color, thickness
    )
    cv2.ellipse(
        img, (x2 - radius, y1 + radius),
        (radius, radius), 270, 0, 90, color, thickness
    )
    cv2.ellipse(
        img, (x1 + radius, y2 - radius),
        (radius, radius), 90, 0, 90, color, thickness
    )
    cv2.ellipse(
        img, (x2 - radius, y2 - radius),
        (radius, radius), 0, 0, 90, color, thickness
    )


def put_text(frame, name, score, nivel_acesso):
    # Informações apresentadas no painel da câmera
    texts = [
        f"ID: {name}",
        f"Distância: {score:.3f}",
        f"Nível de acesso: {nivel_acesso}"
    ]

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    bg_color = (0, 165, 0)
    text_color = (0, 165, 255)

    # Calcula o espaço necessário para exibir os textos
    text_sizes = [
        cv2.getTextSize(text, font, font_scale, thickness)[0]
        for text in texts
    ]

    max_text_width = max(width for width, _ in text_sizes) + 20
    text_height = sum(height for _, height in text_sizes)
    text_height += (len(texts) - 1) * 10 + 20

    # Posiciona o painel na parte inferior da imagem
    x_puttext = 20
    y_puttext = frame.shape[0] - text_height - 30

    draw_rounded_retangle(
        frame,
        (x_puttext, y_puttext - 10),
        (x_puttext + max_text_width, y_puttext + text_height),
        bg_color,
        radius=10
    )

    # Desenha cada linha no painel
    y_offset = 0

    for text, (_, height) in zip(texts, text_sizes):
        cv2.putText(
            frame,
            text,
            (x_puttext + 10, y_puttext + y_offset + height),
            font,
            font_scale,
            text_color,
            thickness
        )

        y_offset += height + 10


def iniciar_api():
    # Inicia o servidor HTTP da aplicação
    uvicorn.run(
        api.app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
    )


def executar_loop_camera():
    global reconhecimento_em_andamento

    webcam = cv2.VideoCapture(0)

    if not webcam.isOpened():
        print("Não foi possível abrir a câmera.")
        raise SystemExit(1)

    webcam.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Resolução usada para exibir a janela
    display_width, display_height = 320, 240
    frame_count = 0

    try:
        cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Camera", display_width, display_height)

        while webcam.isOpened():
            verificador, frame = webcam.read()

            if not verificador:
                print("Falha ao capturar o vídeo")
                break

            # Disponibiliza o frame para a API
            atualizar_frame(frame)
            frame_count += 1

            # Evita executar o reconhecimento em todos os frames
            if frame_count % 15 == 0:
                iniciar_reconhecimento = False

                with reconhecimento_lock:
                    if not reconhecimento_em_andamento:
                        reconhecimento_em_andamento = True
                        iniciar_reconhecimento = True

                if iniciar_reconhecimento:
                    try:
                        # O reconhecimento ocorre sem bloquear a câmera
                        thread = threading.Thread(
                            target=reconhecer_rosto,
                            args=(frame.copy(),)
                        )
                        thread.start()

                    except Exception as erro:
                        with reconhecimento_lock:
                            reconhecimento_em_andamento = False

                        print("Erro ao iniciar reconhecimento:", erro)

            # Copia os dados compartilhados para exibição
            with estado_interface_lock:
                nome_atual = nome_pessoa
                score_atual = score
                nivel_atual = nivel_acesso

            if nome_atual:
                put_text(frame, nome_atual, score_atual, nivel_atual)

            frame_resized = cv2.resize(
                frame, (display_width, display_height)
            )
            cv2.imshow("Camera", frame_resized)

            # ESC encerra o loop
            if cv2.waitKey(5) == 27:
                break

    finally:
        # Libera a câmera e fecha as janelas mesmo em caso de erro
        webcam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    iniciar_api()

import cv2
from src.usuarios import cadastrar_usuario


def capturar_imagem():
    # Abre a webcam para capturar a foto do cadastro
    webcam = cv2.VideoCapture(0)

    if not webcam.isOpened():
        webcam.release()
        raise RuntimeError("Não foi possível abrir a webcam.")

    print("Posicione o rosto na câmera.")
    print("Pressione ESPAÇO para capturar ou ESC para cancelar.")

    imagem_bytes = None

    try:
        while True:
            sucesso, frame = webcam.read()

            if not sucesso:
                raise RuntimeError("Não foi possível capturar a imagem.")

            cv2.imshow("Cadastro de usuario", frame)
            tecla = cv2.waitKey(1) & 0xFF

            if tecla == 32:  # ESPAÇO captura a imagem
                sucesso, imagem_codificada = cv2.imencode(".jpg", frame)

                if not sucesso:
                    raise RuntimeError("Não foi possível codificar a imagem.")

                # Converte a imagem para bytes para armazená-la no banco
                imagem_bytes = imagem_codificada.tobytes()
                break

            if tecla == 27:  # ESC cancela a captura
                break

    finally:
        webcam.release()
        cv2.destroyAllWindows()

    return imagem_bytes


def cadastrar_pela_webcam():
    # Solicita os dados básicos do novo usuário
    cpf = input("CPF (11 dígitos): ").strip()
    nome = input("Nome completo: ").strip()

    try:
        nivel_acesso = int(input("Nível de acesso (1, 2 ou 3): "))
    except ValueError:
        print("Erro: o nível de acesso deve ser um número.")
        return

    try:
        imagem = capturar_imagem()

        if imagem is None:
            print("Cadastro cancelado.")
            return

        # Envia os dados e a foto para a função de cadastro
        cadastrar_usuario(
            cpf=cpf,
            nome=nome,
            nivel_acesso=nivel_acesso,
            caminho_imagem=f"BYTEA:{cpf}",
            imagem=imagem
        )

        print("Usuário cadastrado com sucesso!")

    except ValueError as erro:
        print(f"Erro: {erro}")
    except Exception as erro:
        print(f"Não foi possível cadastrar o usuário: {erro}")


if __name__ == "__main__":
    cadastrar_pela_webcam()

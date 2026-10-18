import sys
import unittest
from unittest.mock import patch, MagicMock
import numpy as np

# Simular dependências que não devem iniciar durante os testes.
sys.modules.setdefault("api", MagicMock())
sys.modules.setdefault("uvicorn", MagicMock())

# Evitar carregar TensorFlow e DeepFace reais.
deepface_mock = MagicMock()
sys.modules["deepface"] = MagicMock(DeepFace=deepface_mock)

from src import main


class TestAtualizarInterface(unittest.TestCase):

    # Verificar se os dados de uma pessoa reconhecida são armazenados corretamente nas variáveis da interface.
    def test_atualizar_interface_com_dados(self):
        main.atualizar_interface("Caique", 0.25, 2)

        self.assertEqual(main.nome_pessoa, "Caique")
        self.assertEqual(main.score, 0.25)
        self.assertEqual(main.nivel_acesso, 2)

    # Verificar se a interface limpa as informações quando nenhum usuário é informado.
    def test_atualizar_interface_limpa_dados(self):
        main.atualizar_interface()

        self.assertEqual(main.nome_pessoa, "")
        self.assertEqual(main.score, 0)
        self.assertEqual(main.nivel_acesso, 0)


class TestReconhecerRosto(unittest.TestCase):

    def setUp(self):
        main.atualizar_interface()
        main.reconhecimento_em_andamento = True

    def resultado_usuario(
        self,
        autenticado=True,
        id_usuario=1,
        usuario="Caique",
        nivel_acesso=2,
        distancia=0.30,
        mensagem="Nenhuma correspondência encontrada"
    ):
        return {
            "autenticado": autenticado,
            "id_usuario": id_usuario,
            "usuario": usuario,
            "nivel_acesso": nivel_acesso,
            "distancia": distancia,
            "mensagem": mensagem
        }

    # Verificar se os dados do usuário reconhecido são atualizados.
    @patch("src.main.atualizar_estado")
    @patch("src.main.reconhecer_imagem")
    def test_usuario_reconhecido(
        self, reconhecer_imagem, atualizar_estado
    ):
        reconhecer_imagem.return_value = self.resultado_usuario()

        main.reconhecer_rosto(
            np.zeros((100, 100, 3), dtype=np.uint8)
        )

        self.assertEqual(main.nome_pessoa, "Caique")
        self.assertEqual(main.nivel_acesso, 2)
        self.assertEqual(main.score, 0.30)

        atualizar_estado.assert_called_once_with(
            autenticado=True,
            id_usuario=1,
            usuario="Caique",
            nivel_acesso=2,
            distancia=0.30
        )
        reconhecer_imagem.assert_called_once()
        self.assertFalse(main.reconhecimento_em_andamento)

    # Verificar se um resultado sem autenticação limpa a interface.
    @patch("src.main.atualizar_estado")
    @patch("src.main.reconhecer_imagem")
    def test_nenhuma_correspondencia(
        self, reconhecer_imagem, atualizar_estado
    ):
        reconhecer_imagem.return_value = self.resultado_usuario(
            autenticado=False
        )

        main.reconhecer_rosto(
            np.zeros((100, 100, 3), dtype=np.uint8)
        )

        self.assertEqual(main.nome_pessoa, "")
        self.assertEqual(main.score, 0)
        self.assertEqual(main.nivel_acesso, 0)
        atualizar_estado.assert_called_once_with()
        self.assertFalse(main.reconhecimento_em_andamento)

    # Verificar se uma exceção limpa a interface e o estado.
    @patch("src.main.atualizar_estado")
    @patch(
        "src.main.reconhecer_imagem",
        side_effect=RuntimeError("Erro ao processar imagem")
    )
    def test_falha_ao_processar_imagem(
        self, reconhecer_imagem, atualizar_estado
    ):
        main.reconhecer_rosto(
            np.zeros((100, 100, 3), dtype=np.uint8)
        )

        self.assertEqual(main.nome_pessoa, "")
        self.assertEqual(main.score, 0)
        self.assertEqual(main.nivel_acesso, 0)
        atualizar_estado.assert_called_once_with()
        self.assertFalse(main.reconhecimento_em_andamento)

    # Verificar se o indicador é liberado quando ocorre uma exceção.
    @patch(
        "src.main.reconhecer_imagem",
        side_effect=RuntimeError("Erro simulado")
    )
    def test_reconhecimento_libera_estado_ao_finalizar(
        self, reconhecer_imagem
    ):
        main.reconhecer_rosto(
            np.zeros((100, 100, 3), dtype=np.uint8)
        )

        self.assertFalse(main.reconhecimento_em_andamento)

    # Verificar se uma identidade não autenticada não permanece na interface.
    @patch("src.main.atualizar_estado")
    @patch("src.main.reconhecer_imagem")
    def test_usuario_nao_autenticado(
        self, reconhecer_imagem, atualizar_estado
    ):
        reconhecer_imagem.return_value = self.resultado_usuario(
            autenticado=False,
            mensagem="Usuário não autenticado"
        )

        main.atualizar_interface("Pessoa anterior", 0.20, 1)

        main.reconhecer_rosto(
            np.zeros((100, 100, 3), dtype=np.uint8)
        )

        self.assertEqual(main.nome_pessoa, "")
        self.assertEqual(main.score, 0)
        self.assertEqual(main.nivel_acesso, 0)
        atualizar_estado.assert_called_once_with()

    # Verificar se um resultado não autenticado com distância alta é rejeitado.
    @patch("src.main.atualizar_estado")
    @patch("src.main.reconhecer_imagem")
    def test_distancia_acima_do_limite(
        self, reconhecer_imagem, atualizar_estado
    ):
        reconhecer_imagem.return_value = self.resultado_usuario(
            autenticado=False,
            distancia=0.80
        )

        main.atualizar_interface("Pessoa anterior", 0.20, 1)

        main.reconhecer_rosto(
            np.zeros((100, 100, 3), dtype=np.uint8)
        )

        self.assertEqual(main.nome_pessoa, "")
        self.assertEqual(main.score, 0)
        self.assertEqual(main.nivel_acesso, 0)
        atualizar_estado.assert_called_once_with()

    # Verificar o comportamento quando o módulo de reconhecimento informa que não há usuário autenticado.
    @patch("src.main.atualizar_estado")
    @patch("src.main.reconhecer_imagem")
    def test_nenhum_usuario_com_imagem(
        self, reconhecer_imagem, atualizar_estado
    ):
        reconhecer_imagem.return_value = self.resultado_usuario(
            autenticado=False,
            mensagem="Nenhum usuário disponível para reconhecimento"
        )

        main.reconhecer_rosto(
            np.zeros((100, 100, 3), dtype=np.uint8)
        )

        self.assertEqual(main.nome_pessoa, "")
        atualizar_estado.assert_called_once_with()
        self.assertFalse(main.reconhecimento_em_andamento)


class TestDesenho(unittest.TestCase):

    # Verificar se a função de retângulo arredondado desenha as partes retas e os quatro cantos.
    @patch("src.main.cv2.rectangle")
    @patch("src.main.cv2.ellipse")
    def test_draw_rounded_retangle(self, ellipse, rectangle):
        imagem = np.zeros((100, 100, 3), dtype=np.uint8)

        main.draw_rounded_retangle(
            imagem, (10, 10), (80, 80), (0, 255, 0)
        )

        # Espera-se que sejam desenhados dois retângulos e quatro elipses para formar os cantos arredondados.
        self.assertEqual(rectangle.call_count, 2)
        self.assertEqual(ellipse.call_count, 4)

    # Verificar se a função de exibição calcula os tamanhos e desenha as três linhas de informação na imagem.
    @patch("src.main.cv2.putText")
    @patch("src.main.cv2.getTextSize", return_value=((100, 20), 5))
    @patch("src.main.cv2.ellipse")
    @patch("src.main.cv2.rectangle")
    def test_put_text(
        self, rectangle, ellipse, get_text_size, put_text
    ):
        imagem = np.zeros((480, 640, 3), dtype=np.uint8)

        main.put_text(imagem, "Caique", 0.25, 2)

        # Confirmar o cálculo do tamanho e a escrita dos textos.
        self.assertEqual(get_text_size.call_count, 3)
        self.assertEqual(put_text.call_count, 3)


class TestIniciarAPI(unittest.TestCase):

    # Simular uvicorn.run e verificar se a API é iniciada com o endereço, a porta e o nível de log esperados.
    @patch("src.main.uvicorn.run")
    def test_iniciar_api(self, executar):
        main.iniciar_api()

        executar.assert_called_once_with(
            main.api.app,
            host="127.0.0.1",
            port=8000,
            log_level="warning"
        )


class TestCamera(unittest.TestCase):

    # Simular uma câmera indisponível e verificar se a função encerra a execução com código de erro.
    @patch("src.main.cv2.VideoCapture")
    def test_camera_nao_abre(self, video_capture):
        video_capture.return_value.isOpened.return_value = False

        with self.assertRaises(SystemExit) as erro:
            main.executar_loop_camera()

        self.assertEqual(erro.exception.code, 1)

        # Como a câmera não abriu, ela não deve ser liberada pelo bloco de encerramento que só é iniciado depois da abertura.
        video_capture.return_value.release.assert_not_called()


class TestLoopCamera(unittest.TestCase):

    # Limpar os dados da interface antes de cada teste do loop principal da câmera.
    def setUp(self):
        main.atualizar_interface()
        main.reconhecimento_em_andamento = False

    # Simular a captura de um frame e verificar se os dados de um usuário reconhecido são desenhados no vídeo.
    @patch("src.main.cv2.destroyAllWindows")
    @patch("src.main.cv2.waitKey", return_value=27)
    @patch("src.main.cv2.imshow")
    @patch("src.main.cv2.resize", side_effect=lambda frame, tamanho: frame)
    @patch("src.main.cv2.resizeWindow")
    @patch("src.main.cv2.namedWindow")
    @patch("src.main.cv2.VideoCapture")
    def test_exibe_dados_da_pessoa_reconhecida(
        self,
        video_capture,
        named_window,
        resize_window,
        resize,
        imshow,
        wait_key,
        destroy_windows,
    ):
        # Simular uma câmera aberta que retorna um frame válido.
        camera = video_capture.return_value
        camera.isOpened.return_value = True
        camera.read.return_value = (
            True,
            np.zeros((480, 640, 3), dtype=np.uint8),
        )

        # Simular uma pessoa já reconhecida.
        main.atualizar_interface("Caique", 0.25, 2)

        # Substituir a função de desenho para verificar sua chamada.
        with patch("src.main.put_text") as put_text:
            main.executar_loop_camera()

        # Confirmar que os dados corretos foram enviados ao desenho.
        put_text.assert_called_once()
        self.assertEqual(put_text.call_args.args[1:], ("Caique", 0.25, 2))

        # Confirmar a liberação da câmera e o fechamento das janelas.
        camera.release.assert_called_once()
        destroy_windows.assert_called_once()

    # Simular uma falha na leitura do frame e verificar se o loop encerra e libera os recursos utilizados.
    @patch("src.main.cv2.destroyAllWindows")
    @patch("src.main.cv2.waitKey", return_value=0)
    @patch("src.main.cv2.imshow")
    @patch("src.main.cv2.resize", side_effect=lambda frame, tamanho: frame)
    @patch("src.main.cv2.resizeWindow")
    @patch("src.main.cv2.namedWindow")
    @patch("src.main.cv2.VideoCapture")
    def test_falha_ao_capturar_video(
        self,
        video_capture,
        named_window,
        resize_window,
        resize,
        imshow,
        wait_key,
        destroy_windows,
    ):
        camera = video_capture.return_value

        # Simular uma câmera aberta e uma captura malsucedida.
        camera.isOpened.side_effect = [True, True]
        camera.read.return_value = (False, None)

        main.executar_loop_camera()

        # Confirmar o encerramento dos recursos e que nenhum frame foi exibido depois da falha na captura.
        camera.release.assert_called_once()
        destroy_windows.assert_called_once()
        imshow.assert_not_called()

    # Simular uma falha ao iniciar a thread de reconhecimento e verificar se o indicador de execução é liberado.
    @patch("src.main.threading.Thread")
    @patch("src.main.cv2.destroyAllWindows")
    @patch("src.main.cv2.waitKey", return_value=27)
    @patch("src.main.cv2.imshow")
    @patch("src.main.cv2.resize", side_effect=lambda frame, tamanho: frame)
    @patch("src.main.cv2.resizeWindow")
    @patch("src.main.cv2.namedWindow")
    @patch("src.main.cv2.VideoCapture")
    def test_falha_ao_iniciar_thread(
        self,
        video_capture,
        named_window,
        resize_window,
        resize,
        imshow,
        wait_key,
        destroy_windows,
        thread,
    ):
        camera = video_capture.return_value
        camera.isOpened.return_value = True
        camera.read.return_value = (
            True,
            np.zeros((480, 640, 3), dtype=np.uint8),
        )

        # Simular uma exceção quando a thread tenta iniciar.
        thread.return_value.start.side_effect = RuntimeError("Erro simulado")

        # Manter o loop ativo por 15 frames para chegar à tentativa de reconhecimento e encerrar na última chamada.
        wait_key.side_effect = [0] * 14 + [27]

        main.reconhecimento_em_andamento = False

        main.executar_loop_camera()

        # Confirmar a tentativa de iniciar a thread e a recuperação do indicador após a falha.
        thread.return_value.start.assert_called_once()
        self.assertFalse(main.reconhecimento_em_andamento)

        # Confirmar a liberação dos recursos da câmera.
        camera.release.assert_called_once()
        destroy_windows.assert_called_once()


if __name__ == "__main__":
    # Executar todos os testes deste arquivo diretamente.
    unittest.main()

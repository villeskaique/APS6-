import os
import subprocess
import sys
import unittest
from pathlib import Path
import textwrap

# Determinar a pasta raiz do projeto a partir deste arquivo.
PROJETO = Path(__file__).resolve().parent.parent


class TestCamera(unittest.TestCase):

    # Executar o módulo principal em um processo separado, permitindo simular a câmera e suas dependências.
    def executar_main(self, codigo_camera):
        # Remover a indentação desnecessária do código de configuração.
        codigo_camera = textwrap.dedent(codigo_camera).strip()

        # Preparar o código que será executado pelo processo de teste.
        codigo_base = textwrap.dedent(f"""\
            import runpy
            import sys
            import cv2
            from unittest.mock import MagicMock, patch

            # Adicionar os diretórios do projeto ao caminho de importação.
            sys.path.insert(0, {str(PROJETO / "src")!r})
            sys.path.insert(0, {str(PROJETO)!r})

            # Substituir serviços externos por objetos simulados.
            sys.modules["api"] = MagicMock()
            sys.modules["uvicorn"] = MagicMock()
            sys.modules["deepface"] = MagicMock(
                DeepFace=MagicMock()
            )

            # Simular a abertura da câmera sem utilizar o dispositivo real.
            with patch.object(cv2, "VideoCapture") as captura:
                camera = captura.return_value
                # CONFIGURACAO_CAMERA

                try:
                    # Executar o módulo principal como programa.
                    runpy.run_module("src.main", run_name="__main__")
                except SystemExit as erro:
                    # Registrar o código de saída para análise do teste.
                    print("CODIGO_SAIDA:", erro.code)
        """)

        # Indentar o código específico para encaixá-lo no bloco preparado.
        codigo_camera = textwrap.indent(codigo_camera, "    ")

        # Inserir a configuração de câmera definida pelo teste.
        codigo = codigo_base.replace(
            "    # CONFIGURACAO_CAMERA",
            codigo_camera,
        )

        # Configurar o ambiente do processo filho.
        ambiente = os.environ.copy()
        ambiente["PYTHONPATH"] = os.pathsep.join([
            str(PROJETO / "src"),
            str(PROJETO),
        ])

        # Executar o teste isoladamente e capturar sua saída.
        return subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=PROJETO,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=15,
        )

    # Verificar o comportamento do programa quando a câmera não consegue ser aberta.
    def test_camera_nao_abre(self):
        resultado = self.executar_main(
            "camera.isOpened.return_value = False"
        )

        # Juntar a saída padrão e a saída de erros do processo.
        saida = resultado.stdout + resultado.stderr

        # Confirmar que a mensagem esperada foi exibida.
        self.assertIn(
            "Não foi possível abrir a câmera.",
            saida,
            msg=(
                f"Processo terminou com código {resultado.returncode}.\n"
                f"STDOUT:\n{resultado.stdout}\n"
                f"STDERR:\n{resultado.stderr}"
            ),
        )

    # Verificar o comportamento quando a câmera abre, mas não consegue capturar um frame.
    def test_falha_ao_capturar_video(self):
        resultado = self.executar_main(
            "camera.isOpened.return_value = True\n"
            "camera.read.return_value = (False, None)"
        )

        saida = resultado.stdout + resultado.stderr

        # Confirmar que a falha na captura foi identificada.
        self.assertIn(
            "Falha ao capturar o vídeo",
            saida,
            msg=(
                f"Processo terminou com código {resultado.returncode}.\n"
                f"Saída do processo:\n{saida}"
            ),
        )


if __name__ == "__main__":
    # Executar os testes da câmera diretamente pelo arquivo.
    unittest.main()

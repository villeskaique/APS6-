
from threading import Event, Lock, Thread
import time
import cv2

_frame_atual = None
_trava_frame = Lock()
_trava_camera = Lock()
_captura = None
_thread_camera = None
_parar = Event()
_ativa = False

LARGURA = 640
ALTURA = 480
FPS = 20


def atualizar_frame(frame):
    global _frame_atual

    with _trava_frame:
        _frame_atual = frame


def obter_frame_atual():
    with _trava_frame:
        if _frame_atual is None:
            return None

        return _frame_atual.copy()


def camera_ativa():
    with _trava_camera:
        return _ativa


def _loop_camera(captura):
    global _captura, _thread_camera, _ativa, _frame_atual

    intervalo = 1 / FPS

    try:
        while not _parar.is_set():
            inicio = time.monotonic()

            sucesso, frame = captura.read()

            if not sucesso or frame is None:
                time.sleep(0.03)
                continue

            frame = cv2.resize(frame, (LARGURA, ALTURA))
            atualizar_frame(frame)

            restante = intervalo - (time.monotonic() - inicio)
            if restante > 0:
                time.sleep(restante)

    finally:
        captura.release()

        with _trava_frame:
            _frame_atual = None

        with _trava_camera:
            if _captura is captura:
                _captura = None
                _thread_camera = None
                _ativa = False


def iniciar_camera():
    """Abre a webcam sob demanda e inicia a publicação de frames."""
    global _captura, _thread_camera, _ativa

    with _trava_camera:
        if _ativa and _thread_camera and _thread_camera.is_alive():
            return True

        captura = cv2.VideoCapture(0)

        if not captura.isOpened():
            captura.release()
            raise RuntimeError("Não foi possível abrir a câmera.")

        captura.set(cv2.CAP_PROP_FRAME_WIDTH, LARGURA)
        captura.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTURA)
        captura.set(cv2.CAP_PROP_FPS, FPS)

        _parar.clear()
        _captura = captura
        _ativa = True

        _thread_camera = Thread(
            target=_loop_camera,
            args=(captura,),
            name="camera-compartilhada",
            daemon=True,
        )

        _thread_camera.start()
        return True


def parar_camera():
    """Solicita o encerramento da captura e aguarda a webcam ser liberada."""
    global _captura, _thread_camera, _ativa, _frame_atual

    with _trava_camera:
        thread = _thread_camera
        _parar.set()

        if thread is None:
            _ativa = False

            with _trava_frame:
                _frame_atual = None

            return False

    thread.join(timeout=2)

    with _trava_camera:
        if not thread.is_alive():
            _ativa = False
            _captura = None
            _thread_camera = None

    return True

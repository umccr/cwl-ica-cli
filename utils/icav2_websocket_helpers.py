import websocket
from websocket._exceptions import WebSocketTimeoutException, WebSocketBadStatusException
from websocket import create_connection
from pathlib import Path
from bs4 import BeautifulSoup
from contextlib import closing

from utils.logging import get_logger

logger = get_logger()


def write_websocket_to_file(url: str, output_file: Path):
    ws = websocket.WebSocket()
    try:
        ws.connect(url, timeout=30)
    except WebSocketBadStatusException:
        logger.error(f"Couldn't connect to websocket url {url}, try again in a few moments"
                     f"Websocket has likely closed and log is being written to a file")

    with open(output_file, "w") as output_h:
        while True:
            try:
                line = ws.recv_data()[-1].decode()
                output_h.write(line)
            except WebSocketTimeoutException:
                logger.info("Got to the end of the websocket, or the connection timed out?")
                break


def convert_html_to_text(input_file: Path, output_file: Path):
    with open(input_file, "r") as input_h, open(output_file, "w") as output_h:
        output_h.write(BeautifulSoup(input_h, features="lxml").get_text())
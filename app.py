import asyncio
import os
from enum import Enum, auto
from typing import Iterator

from dotenv import load_dotenv
from pygments.lexer import Lexer
from pygments.lexers import get_lexer_by_name
from pygments.token import Token

load_dotenv()
targets = os.getenv('TARGETS').split(',')
SSDP_PORT = 2021

class ParserState(Enum):
    GOT_KEY = auto()
    GOT_VALUE = auto()


class SSDPPacketParser:
    _lexer: Lexer = get_lexer_by_name('ssdp')
    header: str
    payload: dict[str, str]
    _raw_data: str

    def __init__(self, payload: str):
        header = []
        payload_data = [[]]
        tokens: Iterator[tuple[Token, str]] = self._lexer.get_tokens(payload)
        for x in tokens:
            if x[0] == Token.Name.Attribute:
                payload_data[-1].append(x[1])
                break
            header.append(x)
        self.header = (''.join([x[1] for x in header])).strip()
        self._raw_data = payload

        parser_state = ParserState.GOT_KEY

        for x in tokens:
            if parser_state == ParserState.GOT_KEY:
                if x[0] not in Token.Literal:
                    continue
                else:
                    parser_state = ParserState.GOT_VALUE
                    payload_data[-1].append(x[1])
                    payload_data.append([])
            elif parser_state == ParserState.GOT_VALUE:
                if x[0] != Token.Name.Attribute:
                    continue
                else:
                    parser_state = ParserState.GOT_KEY
                    payload_data[-1].append(x[1])
        self.payload = {k:v for k,v in payload_data[:-1]}

    def dump(self) -> bytes:
        return ('\r\n'.join([
            self.header,
            *[f"{k}: {v}" for k, v in self.payload.items()],
            '\r\n'
        ])).encode('utf-8')

    def __str__(self):
        return self._raw_data

class SSDPRelayProtocol:
    transport: asyncio.DatagramTransport

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        lexer: Lexer = get_lexer_by_name("ssdp")
        message = data.decode()
        msg = SSDPPacketParser(message)
        print('Received %r from %s' % (message, addr))

        for target in targets:
            msg.payload['DevName.bambu.com'] = f"VPN-{msg.payload['DevName.bambu.com']}"
            self.transport.sendto(msg.dump(), (target, SSDP_PORT))

    def error_received(self, exc):
        print(exc)

async def main():
    print("Starting UDP server")

    # Get a reference to the event loop as we plan to use
    # low-level APIs.
    loop = asyncio.get_running_loop()

    # One protocol instance will be created to serve all
    # client requests.
    transport, protocol = await loop.create_datagram_endpoint(
        SSDPRelayProtocol,
        local_addr=('0.0.0.0', 2021))
    try:
        await asyncio.Event().wait()  # wait here until the Universe ends
    finally:
        transport.close()

asyncio.run(main())
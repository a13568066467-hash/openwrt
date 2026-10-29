#!/usr/bin/env python3
import socket
import time

LOCAL = "192.168.1.125"
HOSTS = ("192.168.1.1", "192.168.10.1")


def try_http(host: str, timeout: float = 4.0) -> None:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.bind((LOCAL, 0))
        s.connect((host, 80))
        s.sendall(f"GET / HTTP/1.0\r\nHost: {host}\r\n\r\n".encode())
        data = b""
        while True:
            try:
                c = s.recv(4096)
            except TimeoutError:
                break
            if not c:
                break
            data += c
            if len(data) > 800:
                break
        print(f"HTTP {host} OK bytes={len(data)}")
        print(data[:400])
    except Exception as e:
        print(f"HTTP {host} FAIL: {e}")
    finally:
        s.close()


def try_ssh(host: str, timeout: float = 4.0) -> None:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.bind((LOCAL, 0))
        s.connect((host, 22))
        ban = s.recv(80)
        print(f"SSH {host} OK {ban!r}")
    except Exception as e:
        print(f"SSH {host} FAIL: {e}")
    finally:
        s.close()


def main() -> None:
    for i in range(12):
        print(f"=== attempt {i+1} ===")
        for host in HOSTS:
            try_ssh(host)
            try_http(host)
        time.sleep(5)


if __name__ == "__main__":
    main()

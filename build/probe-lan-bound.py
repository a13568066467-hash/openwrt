#!/usr/bin/env python3
import socket
import sys

src = "192.168.1.125"
dst = "192.168.1.1"

for port in (22, 80, 443):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try:
        s.bind((src, 0))
        s.connect((dst, port))
        print(f"TCP {dst}:{port} OK from {src}")
        if port == 80:
            s.sendall(b"GET / HTTP/1.0\r\nHost: 192.168.1.1\r\n\r\n")
            data = s.recv(800)
            print(data[:400])
    except Exception as e:
        print(f"TCP {dst}:{port} FAIL: {e}")
    finally:
        s.close()

# Also try FAS self
s = socket.socket()
s.settimeout(3)
try:
    s.bind((src, 0))
    s.connect((src, 8080))
    s.sendall(b"GET /health HTTP/1.0\r\nHost: 192.168.1.125\r\n\r\n")
    print("FAS:", s.recv(200))
except Exception as e:
    print("FAS FAIL:", e)
finally:
    s.close()

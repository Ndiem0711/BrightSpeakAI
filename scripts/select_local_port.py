"""Pick an unused loopback port without touching unrelated processes.
Exit status 2 means all candidates failed. Port selection has unavoidable
check-to-use race; bootstrap's health check catches rare conflicts.
"""
import argparse
import socket
import sys

def port_is_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            probe.bind((host, port))
            probe.listen(1)
        return True
    except OSError:
        return False

def choose_port(host: str = '127.0.0.1', preferred: int = 8765, max_tries: int = 40) -> int:
    if not 1024 <= preferred <= 65535:
        raise ValueError('Preferred port out of range')
    for port in range(preferred, min(65536, preferred + max_tries)):
        if port_is_available(host, port):
            return port
    raise RuntimeError('No free port available in requested range')

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--preferred',type=int,default=8765)
    p.add_argument('--max-tries',type=int,default=40)
    ns=p.parse_args()
    try: print(choose_port(ns.host,ns.preferred,ns.max_tries))
    except (ValueError,RuntimeError) as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)

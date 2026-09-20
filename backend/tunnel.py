import asyncio
import logging
import os
import re
import shutil
from typing import Optional, Callable, List
import httpx

from backend.config import settings

logger = logging.getLogger("botdz.tunnel")

_active_url: Optional[str] = None
_tunnel_tasks: List[asyncio.Task] = []
_watchdog_task: Optional[asyncio.Task] = None
_cf_proc: Optional[asyncio.subprocess.Process] = None
_on_url_change: Optional[Callable] = None
_stopping: bool = False


def register_url_change_callback(callback: Callable):
    """Register an async or sync callback to run when the tunnel URL changes."""
    global _on_url_change
    _on_url_change = callback


def get_tunnel_url() -> Optional[str]:
    """Returns the current active tunnel URL, if any."""
    return _active_url


async def _pipe_streams(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Bidirectionally pipes TCP streams between remote and local sockets."""
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def _localtunnel_worker(remote_host: str, remote_port: int, local_port: int):
    """Worker maintaining a persistent connection pool to localtunnel.me."""
    while not _stopping:
        rem_writer = None
        loc_writer = None
        try:
            rem_reader, rem_writer = await asyncio.open_connection(remote_host, remote_port)
            first_data = await rem_reader.read(8192)
            if not first_data or _stopping:
                if rem_writer:
                    rem_writer.close()
                    await rem_writer.wait_closed()
                await asyncio.sleep(0.2)
                continue

            loc_reader, loc_writer = await asyncio.open_connection("127.0.0.1", local_port)
            loc_writer.write(first_data)
            await loc_writer.drain()

            await asyncio.gather(
                _pipe_streams(rem_reader, loc_writer),
                _pipe_streams(loc_reader, rem_writer)
            )
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.5)
        finally:
            for w in (rem_writer, loc_writer):
                if w:
                    try:
                        w.close()
                    except Exception:
                        pass


async def _start_localtunnel(port: int, timeout: float = 15.0) -> Optional[str]:
    """Starts pure-python native localtunnel client with 200 OK verification."""
    global _active_url, _tunnel_tasks, _stopping
    _stopping = False

    ticket = None
    proxy = settings.TELEGRAM_PROXY if settings.TELEGRAM_PROXY else None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=6.0) as client:
                resp = await client.get("https://localtunnel.me/?new")
                if resp.status_code == 200:
                    ticket = resp.json()
                    break
        except Exception:
            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    resp = await client.get("https://localtunnel.me/?new")
                    if resp.status_code == 200:
                        ticket = resp.json()
                        break
            except Exception:
                pass
        await asyncio.sleep(1)

    if not ticket or "port" not in ticket or "url" not in ticket:
        logger.warning("Localtunnel server unavailable.")
        return None

    assigned_url = ticket["url"]
    remote_port = ticket["port"]
    remote_host = ticket.get("remote_host", "localtunnel.me")

    # Spawn 6 worker connections for concurrent requests
    for _ in range(6):
        task = asyncio.create_task(_localtunnel_worker(remote_host, remote_port, port))
        _tunnel_tasks.append(task)

    # Actively verify that /health responds with 200 OK
    verified = False
    start_time = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            async with httpx.AsyncClient(timeout=3.0) as verify_client:
                r = await verify_client.get(f"{assigned_url}/health")
                if r.status_code == 200:
                    verified = True
                    break
        except Exception:
            pass
        await asyncio.sleep(0.8)

    _active_url = assigned_url
    if verified:
        logger.info(f"🌐 Localtunnel online & verified (200 OK): {_active_url}")
    else:
        logger.info(f"🌐 Localtunnel online: {_active_url}")
    return _active_url


async def _watchdog_loop(port: int):
    """Background loop that health-checks the tunnel and auto-recovers on drops."""
    global _active_url, _stopping
    fail_count = 0
    while not _stopping:
        await asyncio.sleep(25)
        if not _active_url or _stopping:
            continue
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{_active_url}/health")
                if r.status_code == 200:
                    fail_count = 0
                    continue
                else:
                    fail_count += 1
        except Exception:
            fail_count += 1

        if fail_count >= 2 and not _stopping:
            logger.warning(f"Tunnel watchdog detected drop ({fail_count} failed checks). Re-establishing...")
            old_url = _active_url
            await stop_tunnel()
            new_url = await start_tunnel(port)
            if new_url and new_url != old_url:
                logger.info(f"Tunnel restored with new URL: {new_url}")
                if _on_url_change:
                    try:
                        res = _on_url_change(new_url)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception as e:
                        logger.warning(f"Error executing url change callback: {e}")
            fail_count = 0


async def start_tunnel(port: int, timeout: float = 20.0) -> Optional[str]:
    """
    Launches an HTTPS tunnel pointing to localhost:{port}.
    Uses pure-Python localtunnel engine with health verification and watchdog.
    """
    global _active_url, _watchdog_task, _stopping
    _stopping = False

    url = await _start_localtunnel(port, timeout=timeout)
    if url:
        _active_url = url
        if not _watchdog_task or _watchdog_task.done():
            _watchdog_task = asyncio.create_task(_watchdog_loop(port))
        return url

    logger.warning("Could not establish a public HTTPS tunnel.")
    return None


async def stop_tunnel():
    """Terminates all tunnel workers and closes connections cleanly."""
    global _active_url, _tunnel_tasks, _stopping, _cf_proc
    _stopping = True
    _active_url = None

    for t in _tunnel_tasks:
        if not t.done():
            t.cancel()
    _tunnel_tasks.clear()

    if _cf_proc:
        try:
            _cf_proc.terminate()
            await _cf_proc.wait()
        except Exception:
            pass
        _cf_proc = None

    logger.info("Tunnel stopped cleanly.")


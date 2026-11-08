"""Propagate browser/Tool HTTP disconnects to read-only ASGI operations."""
import asyncio

from .study_deadline import is_study_path


class StudyDisconnectMiddleware:
    def __init__(self, app, prefix=''):
        self.app, self.prefix = app, prefix

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '').removeprefix(self.prefix)
        if scope['type'] != 'http' or not (is_study_path(path) or
                scope.get('method') == 'GET' and path == '/api/v1/auth/session'):
            return await self.app(scope, receive, send)
        incoming = asyncio.Queue(maxsize=1)
        disconnected = asyncio.Event()

        async def pump():
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    disconnected.set()
                    return
                await incoming.put(message)

        async def connected_send(message):
            if disconnected.is_set():
                raise asyncio.CancelledError()
            await send(message)

        tasks = [asyncio.create_task(self.app(scope, incoming.get, connected_send)),
                 asyncio.create_task(pump()), asyncio.create_task(disconnected.wait())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if tasks[0] in done:
                return await tasks[0]
            # No response or new upstream operation is allowed after disconnect.
            tasks[0].cancel()
            await asyncio.gather(tasks[0], return_exceptions=True)
            if tasks[1] in done: await tasks[1]
        finally:
            for task in tasks:
                if not task.done(): task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

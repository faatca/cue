from starlette.routing import Route, WebSocketRoute


class RouteHelper:
    def __init__(self):
        self.routes = []

    def get(self, path):
        def decorator(func):
            route = Route(path, func, methods=["GET"])
            self.routes.append(route)
        return decorator

    def post(self, path):
        def decorator(func):
            route = Route(path, func, methods=["POST"])
            self.routes.append(route)
        return decorator

    def put(self, path):
        def decorator(func):
            route = Route(path, func, methods=["PUT"])
            self.routes.append(route)
        return decorator

    def websocket(self, path):
        def decorator(func):
            route = WebSocketRoute(path, func)
            self.routes.append(route)
        return decorator

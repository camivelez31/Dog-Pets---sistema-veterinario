class Observer:
    def update(self, event_type, data):
        pass


class AuditoriaObserver(Observer):
    def __init__(self, audit_callback):
        self.audit_callback = audit_callback

    def update(self, event_type, data):
        self.audit_callback(
            accion=event_type,
            modulo=data.get("modulo", "Sistema"),
            detalle=data.get("detalle", "")
        )


class NotificationCenter:
    def __init__(self):
        self._observers = []

    def subscribe(self, observer):
        self._observers.append(observer)

    def notify(self, event_type, data):
        for observer in self._observers:
            observer.update(event_type, data)
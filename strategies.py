class PaymentStrategy:
    def procesar_pago(self, monto):
        raise NotImplementedError("Debe implementarse en la subclase")


class EfectivoStrategy(PaymentStrategy):
    def procesar_pago(self, monto):
        return f"Pago en efectivo registrado por ${monto}"


class TarjetaStrategy(PaymentStrategy):
    def procesar_pago(self, monto):
        return f"Pago con tarjeta registrado por ${monto}"


class TransferenciaStrategy(PaymentStrategy):
    def procesar_pago(self, monto):
        return f"Pago por transferencia registrado por ${monto}"


def obtener_estrategia_pago(metodo_pago):
    if metodo_pago == "Efectivo":
        return EfectivoStrategy()
    elif metodo_pago == "Tarjeta":
        return TarjetaStrategy()
    elif metodo_pago == "Transferencia":
        return TransferenciaStrategy()
    else:
        raise ValueError("Método de pago no válido")
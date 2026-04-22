class FacturaBase:
    def get_total(self):
        return 0

    def get_descripcion(self):
        return "Factura base"


class FacturaDecorator:
    def __init__(self, factura):
        self.factura = factura

    def get_total(self):
        return self.factura.get_total()

    def get_descripcion(self):
        return self.factura.get_descripcion()


class ConsultaDecorator(FacturaDecorator):
    def get_total(self):
        return self.factura.get_total() + 50000

    def get_descripcion(self):
        return self.factura.get_descripcion() + " + Consulta"


class VacunaDecorator(FacturaDecorator):
    def get_total(self):
        return self.factura.get_total() + 30000

    def get_descripcion(self):
        return self.factura.get_descripcion() + " + Vacuna"


class GuarderiaDecorator(FacturaDecorator):
    def get_total(self):
        return self.factura.get_total() + 40000

    def get_descripcion(self):
        return self.factura.get_descripcion() + " + Guardería"


class BanoDecorator(FacturaDecorator):
    def get_total(self):
        return self.factura.get_total() + 25000

    def get_descripcion(self):
        return self.factura.get_descripcion() + " + Baño"


class DesparasitacionDecorator(FacturaDecorator):
    def get_total(self):
        return self.factura.get_total() + 20000

    def get_descripcion(self):
        return self.factura.get_descripcion() + " + Desparasitación"
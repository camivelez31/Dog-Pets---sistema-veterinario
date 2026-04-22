class MascotaFactory:
    @staticmethod
    def crear(nombre, especie, raza, edad, cliente_id):
        return {
            "nombre": nombre.strip(),
            "especie": especie.strip(),
            "raza": raza.strip() if raza else "",
            "edad": int(edad) if edad else None,
            "cliente_id": int(cliente_id)
        }


class EmpleadoFactory:
    @staticmethod
    def crear(nombre, usuario, password, rol, estado="Activo"):
        return {
            "nombre": nombre.strip(),
            "usuario": usuario.strip(),
            "password": password.strip(),
            "rol": rol.strip(),
            "estado": estado.strip()
        }


class FacturaFactory:
    @staticmethod
    def crear(cliente_id, mascota_id, estado="Pendiente", total=0):
        return {
            "cliente_id": int(cliente_id),
            "mascota_id": int(mascota_id),
            "estado": estado,
            "total": float(total)
        }
import subprocess
import getpass

print("Creando base de datos mcp_prototype")

password = getpass.getpass("Contraseña de MariaDB (root): ")

result = subprocess.run(
    ["mariadb", "-u", "root", f"-p{password}"],
    input=open("db/schema.sql").read(),
    capture_output=True,
    text=True
)

if result.returncode == 0:
    print("Base de datos creada exitosamente.")
else:
    print("Error:")
    print(result.stderr)


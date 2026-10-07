# Tron: Lightcycle Arena

Juego multijugador inspirado en Tron, implementado en Python. Un jugador inicia una sala y los demás se conectan desde la misma red local o desde equipos que puedan alcanzar la dirección IP del servidor. La partida admite de 2 a 6 jugadores.

## Requisitos

- Python 3.10 o posterior.
- `tkinter`, incluido habitualmente con Python para Windows y macOS. En Debian/Ubuntu puede instalarse con `sudo apt install python3-tk`.
- Acceso de red al puerto TCP `5050` del equipo servidor.
- El juego no requiere paquetes de terceros en tiempo de ejecucion ni base de datos.

## Instalación y ejecución

Descarga o copia la carpeta completa en cada equipo. Python debe estar instalado y disponible como `python` en Windows o `python3` en Linux/macOS.

1. En el equipo que alojará la partida, ejecuta `iniciar_servidor.bat` en Windows o `./iniciar_servidor.sh` en Linux/macOS. También puedes usar `python server.py` o `python3 server.py`.
2. Si los jugadores están en otros equipos, permite conexiones TCP entrantes al puerto `5050` en el firewall del servidor. Los equipos deben poder comunicarse entre sí; una conexión a través de Internet también requiere configurar el router y su firewall.
3. En cada equipo jugador, ejecuta `iniciar_cliente.bat` en Windows o `./iniciar_cliente.sh` en Linux/macOS. Alternativamente: `python client.py` o `python3 client.py`.
4. En el cliente, introduce la IP del servidor, el puerto y el nombre del piloto; pulsa **CONECTAR**.
5. Cuando haya al menos dos jugadores en la sala, cualquiera puede pulsar **INICIAR CARRERA**. Gana la última moto que siga en pista. Cuando termina una ronda, cualquier jugador conectado puede iniciar otra.

Para probar en un solo equipo, inicia el servidor y abre tres instancias de `client.py`, cada una con un nombre distinto.

## Crear ejecutables

Los ejecutables se deben construir en el mismo sistema operativo donde se usaran. El instalador prepara un entorno Python aislado, descarga PyInstaller y genera el cliente y el servidor; requiere Python 3.10 o posterior e Internet durante la compilacion.

- **Windows:** ejecuta `instalar_windows.bat`. Los archivos `TronCliente.exe` y `TronServidor.exe` quedan en `dist/windows`. Para ejecutar la compilacion se necesita Python con Tcl/Tk incluido.
- **Linux:** ejecuta `./instalar_linux.sh`. Si el archivo no tiene permiso de ejecucion, primero ejecuta `chmod +x instalar_linux.sh`. Se requiere Tkinter y el modulo `venv`; en Debian/Ubuntu pueden instalarse con `sudo apt install python3-tk python3-venv`. Los ejecutables quedan en `dist/linux` y tambien se instalan en `~/.local/share/tron-lightcycle`.

En Linux, el instalador registra **Tron Lightcycle Arena** en el menu de aplicaciones sin abrir una terminal para jugar. **Tron Lightcycle Server** abre una terminal para mostrar el estado del servidor y permitir detenerlo. En Windows, abre `TronCliente.exe` para jugar y `TronServidor.exe` para alojar la partida. El servidor requiere permitir conexiones TCP entrantes al puerto `5050`.

Los instaladores no descargan ni instalan Python ni componentes del sistema operativo; estos deben estar presentes antes de compilar. PyInstaller y sus paquetes de compilacion se instalan dentro de `.build-venv`, sin modificar la instalacion global de Python.

### Opciones de línea de comandos

El servidor escucha en todas las interfaces de red por omisión:

```text
python server.py --host 0.0.0.0 --port 5050 --tick-rate 10
```

El cliente puede abrirse con valores iniciales distintos; también puedes editarlos en la ventana:

```text
python client.py --host 192.168.1.20 --port 5050 --name Ada
```

El servidor acepta entre 1 y 30 pasos por segundo; el valor inicial es 10. Presiona `Ctrl+C` en la terminal del servidor para detenerlo.

## Controles

- Flechas o `W`, `A`, `S`, `D`: girar. No se permite invertir la dirección directamente.
- Evita los bordes y todas las estelas, incluida la propia.
- La partida termina cuando queda como máximo un piloto con vida.

## Pruebas

Desde la carpeta del proyecto:

```text
python -m unittest discover -s tests -v
```

Las pruebas verifican reglas de juego y una sesión de integración con tres clientes TCP conectados al mismo servidor.

## Archivos principales

- `server.py`: servidor TCP, aceptación de conexiones, hilos de clientes y simulación.
- `client.py`: aplicación gráfica de escritorio y controles del jugador.
- `game.py`: modelo autoritativo y reglas de movimiento/colisión.
- `docs/arquitectura.md`: diagramas, diseño de clases y protocolo de red.

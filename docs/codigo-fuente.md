# Referencia del código fuente

Esta guía acompaña a los docstrings de los módulos y explica cómo se relacionan las reglas de la partida con los mensajes de red. La instalación y el uso para jugadores están en el README; los diagramas de componentes y clases están en [arquitectura.md](arquitectura.md).

## Módulos

- `game.py` contiene el estado de la sala y las reglas. No importa sockets ni Tkinter.
- `server.py` valida los eventos recibidos, modifica el estado compartido y transmite las instantáneas.
- `client.py` administra la ventana, envía acciones y representa el último estado recibido. No decide colisiones ni posiciones por cuenta propia.

## Ciclo de una ronda

La sala comienza en `lobby`. El servidor asigna a cada conexión un identificador y una posición inicial disponible. Con al menos dos jugadores, cualquier cliente puede solicitar `start`; el servidor valida la solicitud y cambia la fase a `running`.

En cada paso, `GameState.tick()` calcula primero el destino de cada piloto activo. Después resuelve los choques y actualiza a quienes sobrevivieron. Se elimina a una moto si sale de la cuadrícula, toca cualquier estela o comparte destino con otra. Cuando queda como máximo una moto activa, la fase pasa a `finished`. Desde ahí se puede solicitar `restart`; el servidor retira primero a quienes ya se desconectaron y restablece el resto.

## Protocolo de aplicación

La conexión usa TCP. Cada mensaje es un objeto JSON codificado en UTF-8 y termina con un salto de línea; el primer mensaje del cliente debe ser `join`.

| Dirección | Tipo | Campos principales | Propósito |
| --- | --- | --- | --- |
| Cliente a servidor | `join` | `name` | Solicita entrar a la sala. |
| Cliente a servidor | `direction` | `direction` | Programa `up`, `down`, `left` o `right` para el siguiente paso. |
| Cliente a servidor | `start` | — | Solicita comenzar la ronda. |
| Cliente a servidor | `restart` | — | Solicita preparar otra ronda terminada. |
| Servidor a cliente | `welcome` | `player_id`, `snapshot` | Confirma el ingreso y asigna identidad. |
| Servidor a cliente | `state` | `snapshot` | Publica el estado actual de la sala. |
| Servidor a cliente | `error` | `message` | Informa un evento o saludo inválido. |

Ejemplo de ingreso:

```json
{"type":"join","name":"Ada"}
```

Una instantánea incluye la fase, las dimensiones del tablero, el ganador y la lista de pilotos. Cada piloto contiene su identificador, nombre, color, posición, estado de vida y estela. Los clientes usan esa información para dibujar el tablero y habilitar los controles correspondientes.

## Hilos y estado compartido

`GameServer` mantiene el modelo. Su hilo de aceptación crea un hilo para atender cada cliente; otro hilo avanza el juego y transmite instantáneas. El bloqueo del servidor serializa el acceso al modelo para que la lectura de un comando no se mezcle con un paso de simulación. Cada conexión usa además un bloqueo de envío para que dos hilos no intercalen bytes en el mismo socket.

En el cliente, `NetworkClient` recibe bytes en un hilo secundario y deposita mensajes en una cola. `TronClientApp._poll_events()` consume esa cola desde el bucle de Tkinter, que es el único hilo que actualiza widgets. Los controles de dirección se envían como intenciones; la respuesta del servidor determina el siguiente estado visible.

## Criterios para mantener el código

- Mantén las reglas de movimiento y colisión en `GameState`; la interfaz no debe duplicarlas.
- Valida los eventos y modifica el estado compartido desde el servidor.
- Describe en docstrings el propósito, las restricciones y los errores que importan para quien llama a una función. En métodos con contrato relevante, incluye argumentos, retorno y excepciones.
- Usa comentarios breves para explicar decisiones que no se deducen del código, como el orden de resolución simultánea o la necesidad de un bloqueo. Evita comentarios que repitan una instrucción evidente.
- Si cambia un tipo de mensaje, una fase o una regla, actualiza este documento y la sección relacionada de arquitectura o instalación.

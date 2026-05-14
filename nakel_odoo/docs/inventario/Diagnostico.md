Contexto (hoy 13 may 2026, master_dev, log /var/log/odoo/odoo.log)
En el vault no hay documentación específica de barcode; el análisis sale del log en vivo y del módulo estándar stock_barcode (rutas bajo /stock_barcode/...).

**Proxy inverso Traefik:** IP **192.168.1.56** (si el tráfico pasa por Traefik, en el log de Odoo la IP origen puede verse como la del proxy o la del cliente según cabeceras `X-Forwarded-For` / configuración del entrypoint).

Quién parece ser “Bruno” en red
192.168.1.62: casi todo el tráfico /stock_barcode/* (móvil / pistola en la LAN). Es el candidato fuerte al dispositivo de picking con barcode.
192.168.1.57: mucho stock.picking en la web (web_search_read, web_save, button_validate, olas, backorder). Otro operador o la misma oficina en escritorio, en paralelo.
Si Bruno es solo .62, lo siguiente aplica directo a él.

Hallazgo principal: muchas lecturas, casi ningún “guardar”
Endpoints relevantes (Enterprise stock_barcode):

POST /stock_barcode/get_specific_barcode_data → consulta / resolución de lo escaneado (muchas veces al día).
POST /stock_barcode/save_barcode_data → persistencia “gorda” de lo que hizo el cliente barcode.
POST /stock_barcode/get_barcode_data → carga inicial del flujo (más pesada, ~1–1,6 s en tus líneas).
Para 192.168.1.62 el 13-may:

Hay decenas de get_specific_barcode_data entre ~13:10 y ~14:10.
Solo aparece una línea de save_barcode_data para esa IP: 13:25:48 (y muchas stock.move.line/web_read justo después).
Otro dispositivo 192.168.1.189 sí tiene varios save_barcode_data el mismo día.

Interpretación: en la franja que miramos, Bruno (.62) está consultando el servidor muchísimo pero casi no está ejecutando el guardado batch que deja cantidades en BD. Eso encaja con “pico y no se refleja” o “queda a medias”: la UI puede mostrar algo en memoria o el servidor responde OK al lookup, pero sin save_barcode_data no hay nada durable (o queda en un paso intermedio).

Concurrencia y escritorio vs pistola
En el mismo rato donde .57 hace muchísimos stock.picking/web_search_read (casi cada segundo entre 14:00 y 14:02) y validaciones:

14:01:28 – usuario #87 borra líneas de movimiento: unlink de stock.move.line 236023, 236295, 236571.
14:01:29 – .62 hace get_specific_barcode_data (pistola).
Justo después, 14:01:53–14:01:54 – .57 hace stock.picking/web_save, button_validate 200.
En el log hay muchos SERIALIZATION_FAILURE en master_dev el mismo día (13:43–14:10 y más), típico de dos transacciones tocando el mismo picking / movimientos. No siempre rompe (Odoo reintenta), pero puede dar lentitud, reintentos y sensación de “inconsistente”.

Otros ruidos el mismo día (no son barcode pero afectan almacén)
14:02:24 – WARNING AFIP WSFE read timeout 60 s mientras .57 está en flujo de albarán.
14:02:29 – button_validate con ~1432 consultas y ~1,7 s real: validación pesada (posible remisión / AFIP / muchas líneas).
Errores push Windows (WNS) y partner autocomplete: red saliente saturada o bloqueada; no explican el scan solo, pero indican problemas de conectividad en el servidor en esa ventana.
Comandos útiles para seguir recogiendo evidencia
# Todo barcode hoy, IP pistola
grep '2026-05-13' /var/log/odoo/odoo.log | grep '192.168.1.62' | grep stock_barcode
# Ratio lectura vs guardado (global hoy)
grep '2026-05-13' /var/log/odoo/odoo.log | grep -c 'get_specific_barcode_data'
grep '2026-05-13' /var/log/odoo/odoo.log | grep -c 'save_barcode_data'
# Conflictos de BD el mismo minuto que un problema
grep '2026-05-13 14:01:' /var/log/odoo/odoo.log | grep SERIALIZATION_FAILURE
# Validaciones y pistola juntas
grep '2026-05-13 14:01:' /var/log/odoo/odoo.log | grep -E '192.168.1.(57|62).*stock\.(picking|barcode)'
Hipótesis ordenadas (para validar con negocio / dev)
No se confirma el paso que dispara save_barcode_data en la app (cierre de línea, “aplicar”, salir del picking, etc.) → muchos escaneos “sueltos” en log.
Dos personas en el mismo picking (.57 + .62) + refresco agresivo del listado → SERIALIZATION_FAILURE y estados que el operador ve “viejos”.
Validación / AFIP lenta o intermitente → pantalla da OK en barcode pero el albarán no termina o queda en wizard (backorder, etc.).
Menos probable solo por log: HTTP 403/500 en barcode; lo que vimos para .62 en esas rutas es casi todo 200.
Próximo paso que más ayuda
En un picking concreto donde “falló”, anotá hora exacta y el nombre del albarán; con eso se puede cruzar .62 vs .57 y ver si hubo save_barcode_data, button_validate o solo get_specific_barcode_data. Si querés, en el siguiente mensaje pasá un número de picking y la ventana de 2–3 minutos y lo volvemos a filtrar fino en el log.
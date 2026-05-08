1) Mover custom addons fuera de la ruta del core (antes del .deb)
Objetivo: que el upgrade del paquete Odoo no “pise” carpetas custom ni te deje un mix raro.

Mover a /opt/odoo/custom-addons los 7 detectados:
droggol_theme_common, theme_prime, modulo_rg5329, nakel_fix_pick, nakel_picking, nakel_wave_picking_link, purchase_flete_markup
Verificar que addons_path incluye /opt/odoo/custom-addons (ya lo tenés).
Reiniciar Odoo.
Validación rápida: login, Inventario, Productos, POS, imprimir un PDF, y revisar logs por Traceback/ERROR.
Por qué primero: si actualizás el .deb antes, te queda más difícil distinguir “qué rompió” (core vs custom), y corrés riesgo de sobrescritura/colisiones.

2) Actualizaciones del sistema (solo Ubuntu packages)
apt-get update + apt-get upgrade (mejor que dist-upgrade para no traer headers/paquetes extra).
Reinicios controlados (al menos postgresql y odoo; o reinicio del CT si tu política lo requiere).
Validación rápida igual que arriba.
Por qué acá: dejás el SO “limpio” (PostgreSQL 14.22, libs TLS, Python packaging updates) antes del salto de Odoo; si aparece un 502, sabés que es de SO/reinicios y no del .deb.

3) Actualizar Odoo con el .deb (último)
Instalar el .deb de Odoo (el 18.0+e.20260424 que analizamos).
Reiniciar Odoo.
Actualizar lista de apps / módulos si corresponde (idealmente solo los necesarios; primero en staging).
Validación funcional (inventario, productos, facturación + PDF/QR, POS, integraciones críticas).
Por qué último: es el cambio más grande en Odoo (código de 1260 módulos core + 96 módulos nuevos en el paquete).
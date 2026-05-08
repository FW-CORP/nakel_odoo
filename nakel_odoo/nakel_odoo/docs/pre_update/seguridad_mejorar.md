2) Los 404 tipo .env, phpinfo.php, wp-admin (botnets) ¿qué hacer?
Sí: son scans automatizados. Y aunque sean 404, sí consumen recursos (TLS + proxy + Odoo worker si llegan hasta Odoo).

Mejor lugar para frenarlo: Traefik (o el proxy edge), no Odoo
En Odoo: se puede, pero es tarde (ya consumió handshake y parte del request) y no tenés geoblocking/rate-limit nativo “fino”.
En Traefik: podés cortar antes, aplicar rate limit, IP allow/deny, fail2ban, y reglas por path/UA sin tocar Odoo.
Qué medidas recomiendo (en orden)
Rate limiting por IP en Traefik para todo lo público.
Bloqueo por paths basura (regex) en Traefik: /.env, /wp-*, *.php, /.aws/*, /.docker/*, etc.
Fail2ban leyendo logs de Traefik (o del proxy): si una IP pega X intentos a esas rutas, ban temporal.
GeoIP “solo Argentina”: solo si estás seguro de que nadie legítimo entra desde fuera (VPN, viajes, soporte, integraciones). Suele ser mejor rate-limit + fail2ban antes que geobloqueo duro.
Nota importante
Si tenés Cloudflare (o similar) delante, muchas de estas cosas son aún más fáciles allí (WAF / country / bot fight).

Si me pasás cómo corre Traefik (docker/compose, systemd, k8s) y dónde están sus middlewares/routers, te digo exactamente qué reglas conviene documentar y dónde colocarlas.
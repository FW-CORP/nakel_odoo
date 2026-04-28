1) wkhtmltopdf en /usr/local/bin/wkhtmltopdf ¿es preocupante?
No necesariamente.
Que Odoo lo detecte en /usr/local/bin solo significa que está usando ese binario (no el del repo de Ubuntu). Es común cuando se instaló una versión “custom”/parcheada.

Lo que sí vale como “señal a revisar”:

Si esa versión es vieja o no parcheada, puede dar los típicos avisos y fallos raros en PDFs.
En tu caso, los checks dan 200, o sea funciona.
Para documentar bien, lo ideal (solo consulta) es registrar wkhtmltopdf --version y si es el “patched qt” recomendado por Odoo. Si querés, lo hacemos después.a


Registrado (solo consulta):

Binario en uso: wkhtmltopdf → /usr/local/bin/wkhtmltopdf (propietario root, fecha 2023-05-21)
Versión: wkhtmltopdf 0.12.6.1 (with patched qt)
Conclusión: esto es lo recomendado para Odoo (el “patched qt”), así que no es preocupante por compatibilidad; al contrario, es lo esperado para PDFs estables.
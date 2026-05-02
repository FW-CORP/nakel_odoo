# Upgrade wkhtmltopdf (patched Qt) — Odoo en Ubuntu 22.04

Este procedimiento instala **wkhtmltopdf con Qt parcheado**, requerido por Odoo para renderizar correctamente:

- Header/Footer HTML de reportes
- Numeración de páginas (`page` / `topage`)
- Logos/estilos en PDFs

Si ves en logs algo como:

> `wkhtmltopdf: ... unpatched qt ... --header-html ... ignored ... --footer-html ... ignored`

entonces **tenés wkhtmltopdf sin parches** y Odoo no podrá usar paginación ni headers/footers como corresponde.

---

## Contexto verificado

- **Servidor**: `dev.nakel` (LXC) `10.5.0.2`
- **OS**: Ubuntu 22.04 (Jammy)
- **Objetivo**: instalar `wkhtmltopdf 0.12.6.1 (with patched qt)`

---

## Pasos (Jammy / amd64)

### 1) Entrar al servidor

```bash
ssh odoo@10.5.0.2
```

### 2) Remover wkhtmltopdf instalado por apt (unpatched)

```bash
sudo apt remove --purge wkhtmltopdf -y
sudo apt autoremove -y
```

> Nota: `autoremove` puede eliminar librerías de Qt/WebKit que quedaron como dependencias del paquete anterior.

### 3) Descargar wkhtmltox “packaging” (patched Qt)

```bash
mkdir -p ~/temp
cd ~/temp
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb
```

### 4) Instalar dependencias mínimas

```bash
sudo apt update
sudo apt install -y xfonts-75dpi xfonts-base fontconfig libxrender1 libjpeg-turbo8
```

### 5) Instalar el .deb

```bash
sudo dpkg -i wkhtmltox_0.12.6.1-3.jammy_amd64.deb || sudo apt -f install -y
```

### 6) Verificar versión (debe decir “patched qt”)

```bash
wkhtmltopdf --version
```

Salida esperada:

```
wkhtmltopdf 0.12.6.1 (with patched qt)
```

### 7) Reiniciar Odoo

```bash
sudo systemctl restart odoo
```

---

## Verificación en logs de Odoo

Al imprimir un reporte PDF, **no debería aparecer** el warning de:

- `unpatched qt`
- `--header-html ... ignored`
- `--footer-html ... ignored`

Si vuelve a aparecer, revisar:

- Qué binario está usando Odoo: `which wkhtmltopdf`
- Que el PATH del servicio incluya `/usr/local/bin` si corresponde
- Que no haya otro `wkhtmltopdf` instalado en paralelo

---

## Tips (si faltan logos/estilos en PDFs)

En Odoo a veces es necesario configurar el parámetro de sistema `report.url` con la URL pública/alcanzable de la instancia (ej. `https://dev.nakel.net.ar`) para que wkhtmltopdf pueda cargar assets.

---

## Referencia

- `wkhtmltopdf/packaging` release `0.12.6.1-3` para Ubuntu 22.04 (Jammy).


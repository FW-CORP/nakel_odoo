# Carga .env (formato KEY=valor, estilo bash) en variables de entorno para Fish.
# Uso (desde la raíz del repo clientes-cc-detalle):
#   source scripts/load-env.fish
if not test -f .env
    echo "load-env.fish: no hay .env en $PWD" >&2
    return 1
end
for line in (command cat .env | string split \n)
    set line (string trim $line)
    if test -z "$line"
        continue
    end
    if string match -q '#*' $line
        continue
    end
    set kv (string split -m 1 = $line)
    if test (count $kv) -ne 2
        continue
    end
    set -gx $kv[1] (string trim $kv[2])
end

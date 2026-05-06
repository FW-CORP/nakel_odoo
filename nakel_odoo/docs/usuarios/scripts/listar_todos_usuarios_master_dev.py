#!/usr/bin/env python3
"""
Script para listar todos los usuarios de MASTER_DEV de forma detallada
Autor: Corolla
Fecha: 2025-08-27
"""

import xmlrpc.client
import json
import logging
from datetime import datetime
import sys
import os

# Agregar el directorio de config_nakel al path
sys.path.append('/mnt/raid5/cursor_files')

try:
    from config_nakel import ODOO_CONFIG_MASTER_DEV
except ImportError:
    print("❌ Error: No se pudo importar config_nakel.py")
    sys.exit(1)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'listado_usuarios_master_dev_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ListadorUsuariosMasterDev:
    def __init__(self):
        self.models = None
        self.uid = None
        
    def conectar_master_dev(self):
        """Conectar a MASTER_DEV"""
        try:
            logger.info(f"🔗 Conectando a: {ODOO_CONFIG_MASTER_DEV['url']}")
            
            common = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG_MASTER_DEV["url"]}/xmlrpc/2/common')
            self.uid = common.authenticate(
                ODOO_CONFIG_MASTER_DEV['db'],
                ODOO_CONFIG_MASTER_DEV['username'],
                ODOO_CONFIG_MASTER_DEV['password'],
                {}
            )
            self.models = xmlrpc.client.ServerProxy(f'{ODOO_CONFIG_MASTER_DEV["url"]}/xmlrpc/2/object')
            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error conectando: {e}")
            return False
    
    def obtener_todos_los_usuarios(self):
        """Obtener todos los usuarios con información detallada"""
        try:
            logger.info("📋 Obteniendo todos los usuarios...")
            
            usuarios_ids = self.models.execute_kw(
                ODOO_CONFIG_MASTER_DEV['db'], self.uid, ODOO_CONFIG_MASTER_DEV['password'],
                'res.users', 'search', [[]]
            )
            
            usuarios = self.models.execute_kw(
                ODOO_CONFIG_MASTER_DEV['db'], self.uid, ODOO_CONFIG_MASTER_DEV['password'],
                'res.users', 'read', [usuarios_ids], {
                    'fields': ['id', 'name', 'login', 'email', 'active', 'partner_id', 'groups_id']
                }
            )
            
            logger.info(f"✅ Obtenidos {len(usuarios)} usuarios")
            return usuarios
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo usuarios: {e}")
            return []
    
    def obtener_grupos_usuarios(self):
        """Obtener información de grupos para mostrar nombres"""
        try:
            grupos_ids = self.models.execute_kw(
                ODOO_CONFIG_MASTER_DEV['db'], self.uid, ODOO_CONFIG_MASTER_DEV['password'],
                'res.groups', 'search', [[]]
            )
            
            grupos = self.models.execute_kw(
                ODOO_CONFIG_MASTER_DEV['db'], self.uid, ODOO_CONFIG_MASTER_DEV['password'],
                'res.groups', 'read', [grupos_ids], {
                    'fields': ['id', 'name', 'category_id']
                }
            )
            
            return {g['id']: g['name'] for g in grupos}
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo grupos: {e}")
            return {}
    
    def mostrar_usuarios_detallado(self):
        """Mostrar usuarios de forma detallada"""
        logger.info("\n📋 LISTADO COMPLETO DE USUARIOS EN MASTER_DEV")
        logger.info("=" * 80)
        
        usuarios = self.obtener_todos_los_usuarios()
        grupos = self.obtener_grupos_usuarios()
        
        if not usuarios:
            logger.error("❌ No se pudieron obtener usuarios")
            return
        
        # Ordenar por ID
        usuarios_ordenados = sorted(usuarios, key=lambda x: x['id'])
        
        logger.info(f"📊 Total de usuarios: {len(usuarios_ordenados)}")
        logger.info("")
        
        for i, usuario in enumerate(usuarios_ordenados, 1):
            logger.info(f"{i:2d}. ID {usuario['id']:3d} | {'✅' if usuario['active'] else '❌'} | {usuario['name']}")
            logger.info(f"     📧 Login: {usuario.get('login', 'N/A')}")
            logger.info(f"     📧 Email: {usuario.get('email', 'N/A')}")
            logger.info(f"     👥 Partner ID: {usuario.get('partner_id', 'N/A')}")
            
            # Mostrar grupos principales
            grupos_usuario = []
            for grupo_id in usuario.get('groups_id', []):
                if grupo_id in grupos:
                    grupos_usuario.append(grupos[grupo_id])
            
            if grupos_usuario:
                logger.info(f"     🔧 Grupos: {', '.join(grupos_usuario[:3])}")  # Solo los primeros 3
                if len(grupos_usuario) > 3:
                    logger.info(f"           ... y {len(grupos_usuario) - 3} más")
            else:
                logger.info(f"     🔧 Grupos: Sin grupos asignados")
            
            logger.info("")
        
        # Mostrar estadísticas
        usuarios_activos = [u for u in usuarios_ordenados if u['active']]
        usuarios_inactivos = [u for u in usuarios_ordenados if not u['active']]
        
        logger.info("📊 ESTADÍSTICAS:")
        logger.info(f"   • Usuarios activos: {len(usuarios_activos)}")
        logger.info(f"   • Usuarios inactivos: {len(usuarios_inactivos)}")
        logger.info(f"   • Total: {len(usuarios_ordenados)}")
        
        # Buscar usuarios que podrían ser vendedores
        posibles_vendedores = []
        for usuario in usuarios_ordenados:
            nombre_lower = usuario['name'].lower()
            if any(palabra in nombre_lower for palabra in ['ventas', 'vendedor', 'comercial', 'sales']):
                posibles_vendedores.append(usuario)
        
        if posibles_vendedores:
            logger.info(f"\n🔍 POSIBLES VENDEDORES DETECTADOS ({len(posibles_vendedores)}):")
            for usuario in posibles_vendedores:
                logger.info(f"   • ID {usuario['id']}: {usuario['name']} ({usuario.get('login', 'N/A')})")
        else:
            logger.info("\n🔍 No se detectaron usuarios con roles de ventas")
        
        return usuarios_ordenados
    
    def buscar_vendedores_especificos(self):
        """Buscar los vendedores específicos mencionados por el usuario"""
        logger.info("\n🔍 BUSCANDO VENDEDORES ESPECÍFICOS MENCIONADOS")
        logger.info("=" * 60)
        
        vendedores_a_buscar = [
            "Chirimonti Jose Luis",
            "Choque Jorge Ariel"
        ]
        
        usuarios = self.obtener_todos_los_usuarios()
        
        for vendedor_nombre in vendedores_a_buscar:
            logger.info(f"\n🔍 Buscando: {vendedor_nombre}")
            
            # Búsqueda exacta
            encontrado = False
            for usuario in usuarios:
                if usuario['name'] == vendedor_nombre:
                    logger.info(f"   ✅ ENCONTRADO: ID {usuario['id']} - {usuario['name']}")
                    logger.info(f"      📧 Login: {usuario.get('login', 'N/A')}")
                    logger.info(f"      📧 Email: {usuario.get('email', 'N/A')}")
                    encontrado = True
                    break
            
            if not encontrado:
                # Búsqueda parcial
                coincidencias = []
                for usuario in usuarios:
                    if any(palabra.lower() in usuario['name'].lower() for palabra in vendedor_nombre.split()):
                        coincidencias.append(usuario)
                
                if coincidencias:
                    logger.info(f"   🔍 Coincidencias parciales encontradas:")
                    for usuario in coincidencias:
                        logger.info(f"      • ID {usuario['id']}: {usuario['name']} ({usuario.get('login', 'N/A')})")
                else:
                    logger.warning(f"   ❌ NO ENCONTRADO: {vendedor_nombre}")
    
    def ejecutar_listado_completo(self):
        """Ejecutar listado completo"""
        if not self.conectar_master_dev():
            return False
        
        # Mostrar usuarios detallado
        usuarios = self.mostrar_usuarios_detallado()
        
        # Buscar vendedores específicos
        self.buscar_vendedores_especificos()
        
        # Crear reporte
        reporte = {
            'fecha_listado': datetime.now().isoformat(),
            'total_usuarios': len(usuarios) if usuarios else 0,
            'usuarios_activos': len([u for u in usuarios if u['active']]) if usuarios else 0,
            'usuarios_inactivos': len([u for u in usuarios if not u['active']]) if usuarios else 0,
            'usuarios': usuarios if usuarios else []
        }
        
        # Guardar reporte
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"listado_completo_usuarios_master_dev_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(reporte, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"\n✅ Reporte guardado: {filename}")
        
        return True

def main():
    """Función principal"""
    listador = ListadorUsuariosMasterDev()
    
    if listador.ejecutar_listado_completo():
        logger.info("\n🎉 ¡LISTADO COMPLETADO!")
    else:
        logger.error("\n❌ Error en el listado")

if __name__ == "__main__":
    main()

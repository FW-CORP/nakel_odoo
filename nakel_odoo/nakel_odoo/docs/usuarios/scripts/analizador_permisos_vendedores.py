#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALIZADOR DE PERMISOS DE VENDEDORES
===================================

Script para analizar si los vendedores pueden ver todos los contactos
o solo los que tienen asignados, después de implementar la solución
para autoservicios.

Autor: Corolla AI Assistant
Fecha: 2025-09-08
"""

import os
import xmlrpc.client
import ssl
import logging
from datetime import datetime

class AnalizadorPermisosVendedores:
    def __init__(self):
        self.logger = self._configurar_logging()
        
    def _configurar_logging(self):
        """Configurar logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def conectar_master_15(self):
        """Conectar a master_15"""
        try:
            self.logger.info("🔌 CONECTANDO A MASTER_15...")
            
            url = os.environ.get("ODOO_URL", "https://nakel.net.ar").strip()
            database = os.environ.get("ODOO_DB", "master_15").strip()
            username = os.environ.get("ODOO_USERNAME", "odoo@nakel.ar").strip()
            password = os.environ.get("ODOO_PASSWORD", "").strip()
            if not password:
                raise RuntimeError(
                    "Falta ODOO_PASSWORD en el entorno. No hardcodear credenciales."
                )
            
            # Contexto SSL
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Conexión
            common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common', context=ssl_context)
            models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object', context=ssl_context)
            
            # Autenticación
            uid = common.authenticate(database, username, password, {})
            if not uid:
                self.logger.error("❌ Error de autenticación")
                return None, None, None
            
            self.logger.info(f"✅ Conectado - UID: {uid}")
            return models, uid, database
            
        except Exception as e:
            self.logger.error(f"❌ Error conectando: {e}")
            return None, None, None
    
    def identificar_vendedores(self, models, uid, database):
        """Identificar vendedores (usuarios con contactos asignados)"""
        try:
            self.logger.info("👥 IDENTIFICANDO VENDEDORES...")
            
            # Obtener usuarios que tienen contactos asignados
            vendedores = models.execute_kw(
                database, uid, password,
                'res.users', 'search_read',
                [[('active', '=', True)], ['id', 'name', 'login', 'email']]
            )
            
            vendedores_con_contactos = []
            
            for vendedor in vendedores:
                # Contar contactos asignados a este vendedor
                contactos_asignados = models.execute_kw(
                    database, uid, password,
                    'res.partner', 'search_count',
                    [[('user_id', '=', vendedor['id'])]]
                )
                
                if contactos_asignados > 0:
                    vendedores_con_contactos.append({
                        'id': vendedor['id'],
                        'name': vendedor['name'],
                        'login': vendedor['login'],
                        'email': vendedor.get('email', 'N/A'),
                        'contactos_asignados': contactos_asignados
                    })
            
            self.logger.info(f"   • Vendedores con contactos asignados: {len(vendedores_con_contactos)}")
            
            for vendedor in vendedores_con_contactos:
                self.logger.info(f"     - {vendedor['name']} (ID: {vendedor['id']}): {vendedor['contactos_asignados']} contactos")
            
            return vendedores_con_contactos
            
        except Exception as e:
            self.logger.error(f"❌ Error identificando vendedores: {e}")
            return []
    
    def identificar_autoservicios(self, models, uid, database):
        """Identificar usuarios del grupo autoservicio_contactos"""
        try:
            self.logger.info("🏪 IDENTIFICANDO AUTOSERVICIOS...")
            
            # Obtener grupo autoservicio_contactos
            grupo = models.execute_kw(
                database, uid, password,
                'res.groups', 'read',
                [[97], ['name', 'users']]  # ID 97 es el grupo que creamos
            )
            
            if grupo:
                grupo_info = grupo[0]
                usuarios_grupo = models.execute_kw(
                    database, uid, password,
                    'res.users', 'read',
                    [grupo_info['users'], ['id', 'name', 'login', 'email']]
                )
                
                self.logger.info(f"   • Usuarios en grupo autoservicio_contactos: {len(usuarios_grupo)}")
                
                for usuario in usuarios_grupo:
                    self.logger.info(f"     - {usuario['name']} (ID: {usuario['id']})")
                
                return usuarios_grupo
            else:
                self.logger.error("   ❌ Grupo autoservicio_contactos no encontrado")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ Error identificando autoservicios: {e}")
            return []
    
    def analizar_permisos_por_usuario(self, models, uid, database, usuarios, tipo_usuario):
        """Analizar permisos de un grupo de usuarios"""
        try:
            self.logger.info(f"🔍 ANALIZANDO PERMISOS DE {tipo_usuario.upper()}...")
            
            total_contactos = models.execute_kw(
                database, uid, password,
                'res.partner', 'search_count',
                [[]]
            )
            
            for usuario in usuarios:
                self.logger.info(f"\n   👤 {usuario['name']} (ID: {usuario['id']})")
                
                # Contar contactos asignados
                contactos_asignados = models.execute_kw(
                    database, uid, password,
                    'res.partner', 'search_count',
                    [[('user_id', '=', usuario['id'])]]
                )
                
                self.logger.info(f"      • Contactos asignados: {contactos_asignados}")
                
                # Verificar acceso a contactos específicos
                contactos_gomez = models.execute_kw(
                    database, uid, password,
                    'res.partner', 'search_count',
                    [[('name', 'ilike', 'GOMEZ JUAN')]]
                )
                
                contactos_caleta = models.execute_kw(
                    database, uid, password,
                    'res.partner', 'search_count',
                    [[('category_id.name', '=', 'Caleta Olivia')]]
                )
                
                self.logger.info(f"      • Puede ver GOMEZ JUAN: {contactos_gomez} contactos")
                self.logger.info(f"      • Puede ver Caleta Olivia: {contactos_caleta} contactos")
                
                # Determinar si tiene acceso completo o restringido
                if contactos_gomez > 0 and contactos_caleta > 0:
                    self.logger.info(f"      ✅ ACCESO COMPLETO: Puede ver todos los contactos")
                elif contactos_asignados > 0:
                    self.logger.info(f"      ⚠️  ACCESO RESTRINGIDO: Solo ve sus contactos asignados")
                else:
                    self.logger.info(f"      ❌ SIN ACCESO: No tiene contactos asignados")
            
        except Exception as e:
            self.logger.error(f"❌ Error analizando permisos: {e}")
    
    def verificar_reglas_activas(self, models, uid, database):
        """Verificar que las reglas estén activas"""
        try:
            self.logger.info("📋 VERIFICANDO REGLAS ACTIVAS...")
            
            reglas = models.execute_kw(
                database, uid, password,
                'ir.rule', 'search_read',
                [[('model_id.model', '=', 'res.partner')], ['id', 'name', 'active', 'domain_force']]
            )
            
            for regla in reglas:
                estado = "✅ ACTIVA" if regla['active'] else "❌ INACTIVA"
                self.logger.info(f"   • {regla['name']} (ID: {regla['id']}): {estado}")
                
                if regla['active']:
                    dominio = regla.get('domain_force', [])
                    if 'user_id' in str(dominio) or 'commercial_partner_id' in str(dominio):
                        self.logger.info(f"     ⚠️  Esta regla restringe acceso por usuario")
            
            return reglas
            
        except Exception as e:
            self.logger.error(f"❌ Error verificando reglas: {e}")
            return []
    
    def ejecutar_analisis_completo(self):
        """Ejecutar análisis completo de permisos"""
        try:
            self.logger.info("🚀 INICIANDO ANÁLISIS COMPLETO DE PERMISOS")
            
            # 1. Conectar
            models, uid, database = self.conectar_master_15()
            if not models:
                return False
            
            # 2. Verificar reglas
            self.logger.info("\n" + "="*60)
            reglas = self.verificar_reglas_activas(models, uid, database)
            
            # 3. Identificar vendedores
            self.logger.info("\n" + "="*60)
            vendedores = self.identificar_vendedores(models, uid, database)
            
            # 4. Identificar autoservicios
            self.logger.info("\n" + "="*60)
            autoservicios = self.identificar_autoservicios(models, uid, database)
            
            # 5. Analizar permisos de vendedores
            self.logger.info("\n" + "="*60)
            self.analizar_permisos_por_usuario(models, uid, database, vendedores, "vendedores")
            
            # 6. Analizar permisos de autoservicios
            self.logger.info("\n" + "="*60)
            self.analizar_permisos_por_usuario(models, uid, database, autoservicios, "autoservicios")
            
            # 7. Resumen final
            self.logger.info("\n" + "="*60)
            self.logger.info("🎯 RESUMEN DEL ANÁLISIS")
            self.logger.info(f"   • Vendedores analizados: {len(vendedores)}")
            self.logger.info(f"   • Autoservicios analizados: {len(autoservicios)}")
            self.logger.info(f"   • Reglas activas: {len([r for r in reglas if r['active']])}")
            
            self.logger.info("\n💡 CONCLUSIÓN:")
            self.logger.info("   • Vendedores: Deberían tener acceso restringido")
            self.logger.info("   • Autoservicios: Deberían tener acceso completo")
            self.logger.info("   • CLAUDIA MANUEL: Debería ver todos los contactos")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error en análisis completo: {e}")
            return False

def main():
    """Función principal"""
    try:
        analizador = AnalizadorPermisosVendedores()
        exito = analizador.ejecutar_analisis_completo()
        
        if exito:
            print(f"\n✅ Análisis de permisos completado exitosamente")
        else:
            print(f"\n❌ Error en el análisis")
        
        return exito
        
    except Exception as e:
        print(f"❌ Error en función principal: {e}")
        return False

if __name__ == "__main__":
    main()















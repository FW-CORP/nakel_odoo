#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BUSCADOR DE USUARIOS Y CONTACTOS
===============================

Script para buscar usuarios y contactos específicos en master_15,
corrigiendo los errores del script anterior.

Autor: Corolla AI Assistant
Fecha: 2025-09-08
"""

import xmlrpc.client
import ssl
import logging
from datetime import datetime

class BuscadorUsuariosContactos:
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
            
            url = "https://nakel.net.ar"
            database = "master_15"
            username = "odoo@nakel.ar"
            password = "REDACTED"
            
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
    
    def buscar_usuarios_por_nombre(self, models, uid, database, nombres):
        """Buscar usuarios por nombre"""
        try:
            self.logger.info("👥 BUSCANDO USUARIOS POR NOMBRE...")
            
            usuarios_encontrados = []
            
            for nombre in nombres:
                self.logger.info(f"   🔍 Buscando: {nombre}")
                
                # Buscar por nombre exacto
                usuarios = models.execute_kw(
                    database, uid, 'REDACTED',
                    'res.users', 'search_read',
                    [[('name', '=', nombre)], ['id', 'name', 'login', 'email', 'active', 'groups_id']]
                )
                
                if not usuarios:
                    # Buscar por nombre que contenga
                    usuarios = models.execute_kw(
                        database, uid, 'REDACTED',
                        'res.users', 'search_read',
                        [[('name', 'ilike', nombre)], ['id', 'name', 'login', 'email', 'active', 'groups_id']]
                    )
                
                if not usuarios:
                    # Buscar por login
                    usuarios = models.execute_kw(
                        database, uid, 'REDACTED',
                        'res.users', 'search_read',
                        [[('login', 'ilike', nombre)], ['id', 'name', 'login', 'email', 'active', 'groups_id']]
                    )
                
                self.logger.info(f"     • Encontrados: {len(usuarios)} usuarios")
                for usuario in usuarios:
                    self.logger.info(f"       - ID: {usuario['id']}, Nombre: {usuario['name']}, Login: {usuario['login']}")
                    self.logger.info(f"         Email: {usuario.get('email', 'N/A')}, Activo: {usuario['active']}")
                    self.logger.info(f"         Grupos: {usuario['groups_id']}")
                    usuarios_encontrados.append(usuario)
                
                self.logger.info("")
            
            return usuarios_encontrados
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando usuarios: {e}")
            return []
    
    def buscar_contactos_por_nombre(self, models, uid, database, nombres):
        """Buscar contactos por nombre"""
        try:
            self.logger.info("👤 BUSCANDO CONTACTOS POR NOMBRE...")
            
            contactos_encontrados = []
            
            for nombre in nombres:
                self.logger.info(f"   🔍 Buscando contacto: {nombre}")
                
                # Buscar por nombre exacto
                contactos = models.execute_kw(
                    database, uid, 'REDACTED',
                    'res.partner', 'search_read',
                    [[('name', '=', nombre)], 
                     ['id', 'name', 'email', 'phone', 'city', 'vat', 'category_id', 'user_id', 'active']]
                )
                
                if not contactos:
                    # Buscar por nombre que contenga
                    contactos = models.execute_kw(
                        database, uid, 'REDACTED',
                        'res.partner', 'search_read',
                        [[('name', 'ilike', nombre)], 
                         ['id', 'name', 'email', 'phone', 'city', 'vat', 'category_id', 'user_id', 'active']]
                    )
                
                self.logger.info(f"     • Encontrados: {len(contactos)} contactos")
                for contacto in contactos:
                    self.logger.info(f"       - ID: {contacto['id']}, Nombre: {contacto['name']}")
                    self.logger.info(f"         Email: {contacto.get('email', 'N/A')}")
                    self.logger.info(f"         Teléfono: {contacto.get('phone', 'N/A')}")
                    self.logger.info(f"         Ciudad: {contacto.get('city', 'N/A')}")
                    self.logger.info(f"         VAT: {contacto.get('vat', 'N/A')}")
                    self.logger.info(f"         Categorías: {contacto.get('category_id', [])}")
                    self.logger.info(f"         Usuario asignado: {contacto.get('user_id', 'N/A')}")
                    self.logger.info(f"         Activo: {contacto.get('active', 'N/A')}")
                    contactos_encontrados.append(contacto)
                
                self.logger.info("")
            
            return contactos_encontrados
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando contactos: {e}")
            return []
    
    def listar_todos_los_usuarios(self, models, uid, database):
        """Listar todos los usuarios del sistema"""
        try:
            self.logger.info("📋 LISTANDO TODOS LOS USUARIOS...")
            
            # Obtener todos los usuarios
            usuarios = models.execute_kw(
                database, uid, 'REDACTED',
                'res.users', 'search_read',
                [[], ['id', 'name', 'login', 'email', 'active']],
                {'limit': 50}
            )
            
            self.logger.info(f"   • Total de usuarios: {len(usuarios)}")
            self.logger.info(f"\n📋 LISTA DE USUARIOS:")
            
            for i, usuario in enumerate(usuarios, 1):
                self.logger.info(f"   {i:2d}. ID: {usuario['id']} - {usuario['name']}")
                self.logger.info(f"       Login: {usuario['login']}")
                self.logger.info(f"       Email: {usuario.get('email', 'N/A')}")
                self.logger.info(f"       Activo: {usuario['active']}")
                self.logger.info("")
            
            return usuarios
            
        except Exception as e:
            self.logger.error(f"❌ Error listando usuarios: {e}")
            return []
    
    def analizar_contactos_por_categoria_detallado(self, models, uid, database):
        """Analizar contactos por categoría con más detalle"""
        try:
            self.logger.info("🏷️ ANÁLISIS DETALLADO POR CATEGORÍA...")
            
            # Obtener categorías con más contactos
            categorias_importantes = ['Caleta Olivia', 'Comodoro Sur', 'Las Heras', 'Puerto Deseado']
            
            for categoria_nombre in categorias_importantes:
                self.logger.info(f"   🔍 Analizando categoría: {categoria_nombre}")
                
                # Buscar la categoría
                categoria = models.execute_kw(
                    database, uid, 'REDACTED',
                    'res.partner.category', 'search_read',
                    [[('name', '=', categoria_nombre)], ['id', 'name']]
                )
                
                if categoria:
                    categoria_id = categoria[0]['id']
                    
                    # Obtener algunos contactos de esta categoría
                    contactos = models.execute_kw(
                        database, uid, 'REDACTED',
                        'res.partner', 'search_read',
                        [[('category_id', 'in', [categoria_id])], 
                         ['id', 'name', 'email', 'phone', 'city', 'vat', 'user_id']],
                        {'limit': 10}
                    )
                    
                    self.logger.info(f"     • Contactos en {categoria_nombre}: {len(contactos)} (mostrando primeros 10)")
                    for contacto in contactos:
                        self.logger.info(f"       - {contacto['name']} (ID: {contacto['id']})")
                        if contacto.get('user_id'):
                            self.logger.info(f"         Usuario asignado: {contacto['user_id']}")
                        if contacto.get('city'):
                            self.logger.info(f"         Ciudad: {contacto['city']}")
                    
                    self.logger.info("")
            
        except Exception as e:
            self.logger.error(f"❌ Error en análisis detallado: {e}")
    
    def ejecutar_busqueda_completa(self):
        """Ejecutar búsqueda completa"""
        try:
            self.logger.info("🚀 INICIANDO BÚSQUEDA COMPLETA DE USUARIOS Y CONTACTOS")
            
            # 1. Conectar
            models, uid, database = self.conectar_master_15()
            if not models:
                return False
            
            # 2. Buscar usuarios específicos
            nombres_usuarios = ['CLAUDIA MANUEL', 'GOMEZ JUAN', 'CLAUDIA', 'MANUEL', 'GOMEZ']
            usuarios = self.buscar_usuarios_por_nombre(models, uid, database, nombres_usuarios)
            
            # 3. Buscar contactos específicos
            nombres_contactos = ['GOMEZ JUAN', 'CLAUDIA MANUEL', 'GOMEZ', 'CLAUDIA']
            contactos = self.buscar_contactos_por_nombre(models, uid, database, nombres_contactos)
            
            # 4. Listar todos los usuarios
            todos_usuarios = self.listar_todos_los_usuarios(models, uid, database)
            
            # 5. Análisis detallado por categoría
            self.analizar_contactos_por_categoria_detallado(models, uid, database)
            
            self.logger.info("\n🎯 BÚSQUEDA COMPLETADA")
            self.logger.info(f"   • Usuarios específicos encontrados: {len(usuarios)}")
            self.logger.info(f"   • Contactos específicos encontrados: {len(contactos)}")
            self.logger.info(f"   • Total de usuarios en sistema: {len(todos_usuarios)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error en búsqueda completa: {e}")
            return False

def main():
    """Función principal"""
    try:
        buscador = BuscadorUsuariosContactos()
        exito = buscador.ejecutar_busqueda_completa()
        
        if exito:
            print(f"\n✅ Búsqueda de usuarios y contactos completada exitosamente")
        else:
            print(f"\n❌ Error en la búsqueda")
        
        return exito
        
    except Exception as e:
        print(f"❌ Error en función principal: {e}")
        return False

if __name__ == "__main__":
    main()















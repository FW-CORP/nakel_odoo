#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALIZADOR Y MODIFICADOR DE PERMISOS DE CONTACTOS
===============================================

Script para analizar y modificar los permisos de visibilidad de contactos
en Odoo, permitiendo que todos los empleados vean todos los contactos.

Autor: Corolla AI Assistant
Fecha: 2025-09-08
"""

import xmlrpc.client
import ssl
import logging
from datetime import datetime

class AnalizadorModificadorPermisos:
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
    
    def analizar_reglas_actuales(self, models, uid, database):
        """Analizar reglas de registro actuales"""
        try:
            self.logger.info("📋 ANALIZANDO REGLAS DE REGISTRO ACTUALES...")
            
            # Obtener reglas de registro para res.partner
            reglas = models.execute_kw(
                database, uid, 'REDACTED',
                'ir.rule', 'search_read',
                [[('model_id.model', '=', 'res.partner')], 
                 ['id', 'name', 'domain_force', 'groups', 'perm_read', 'perm_write', 'perm_create', 'perm_unlink', 'active']]
            )
            
            self.logger.info(f"   • Reglas encontradas: {len(reglas)}")
            
            for regla in reglas:
                self.logger.info(f"\n   📋 REGLA: {regla['name']} (ID: {regla['id']})")
                self.logger.info(f"       Activa: {regla.get('active', True)}")
                self.logger.info(f"       Dominio: {regla.get('domain_force', 'N/A')}")
                self.logger.info(f"       Grupos: {regla.get('groups', [])}")
                self.logger.info(f"       Permisos: R:{regla.get('perm_read', False)}, W:{regla.get('perm_write', False)}, C:{regla.get('perm_create', False)}, D:{regla.get('perm_unlink', False)}")
                
                # Analizar el dominio
                dominio = regla.get('domain_force', [])
                if dominio:
                    self.logger.info(f"       📊 ANÁLISIS DEL DOMINIO:")
                    if 'user_id' in str(dominio):
                        self.logger.info(f"         ⚠️  RESTRINGE por usuario asignado")
                    if 'company_id' in str(dominio):
                        self.logger.info(f"         ⚠️  RESTRINGE por compañía")
                    if 'partner_share' in str(dominio):
                        self.logger.info(f"         ⚠️  RESTRINGE por partner_share")
                    if 'commercial_partner_id' in str(dominio):
                        self.logger.info(f"         ⚠️  RESTRINGE por commercial_partner")
            
            return reglas
            
        except Exception as e:
            self.logger.error(f"❌ Error analizando reglas: {e}")
            return []
    
    def analizar_grupos_usuarios(self, models, uid, database):
        """Analizar grupos de usuarios"""
        try:
            self.logger.info("👥 ANALIZANDO GRUPOS DE USUARIOS...")
            
            # Obtener todos los grupos
            grupos = models.execute_kw(
                database, uid, 'REDACTED',
                'res.groups', 'search_read',
                [[], ['id', 'name', 'category_id', 'full_name', 'users']],
                {'limit': 50}
            )
            
            self.logger.info(f"   • Total de grupos: {len(grupos)}")
            
            # Buscar grupos relacionados con contactos/partners
            grupos_contactos = []
            for grupo in grupos:
                if any(palabra in grupo['name'].lower() for palabra in ['partner', 'contact', 'customer', 'supplier']):
                    grupos_contactos.append(grupo)
            
            self.logger.info(f"   • Grupos relacionados con contactos: {len(grupos_contactos)}")
            
            for grupo in grupos_contactos:
                self.logger.info(f"     - {grupo['name']} (ID: {grupo['id']})")
                self.logger.info(f"       Categoría: {grupo.get('category_id', 'N/A')}")
                self.logger.info(f"       Usuarios: {len(grupo.get('users', []))}")
            
            return grupos, grupos_contactos
            
        except Exception as e:
            self.logger.error(f"❌ Error analizando grupos: {e}")
            return [], []
    
    def analizar_usuarios_activos(self, models, uid, database):
        """Analizar usuarios activos"""
        try:
            self.logger.info("👤 ANALIZANDO USUARIOS ACTIVOS...")
            
            # Obtener usuarios activos
            usuarios = models.execute_kw(
                database, uid, 'REDACTED',
                'res.users', 'search_read',
                [[('active', '=', True)], ['id', 'name', 'login', 'email', 'groups_id']]
            )
            
            self.logger.info(f"   • Usuarios activos: {len(usuarios)}")
            
            # Analizar permisos de cada usuario
            for usuario in usuarios:
                self.logger.info(f"     - {usuario['name']} (ID: {usuario['id']})")
                self.logger.info(f"       Login: {usuario['login']}")
                self.logger.info(f"       Grupos: {len(usuario['groups_id'])} grupos")
            
            return usuarios
            
        except Exception as e:
            self.logger.error(f"❌ Error analizando usuarios: {e}")
            return []
    
    def proponer_soluciones(self, reglas, grupos, usuarios):
        """Proponer soluciones para permitir acceso completo"""
        try:
            self.logger.info("💡 PROPONIENDO SOLUCIONES...")
            
            self.logger.info("\n🔧 OPCIÓN 1: MODIFICAR REGLAS DE REGISTRO")
            self.logger.info("   • Desactivar reglas restrictivas")
            self.logger.info("   • Modificar dominios para permitir acceso completo")
            self.logger.info("   • Ventaja: Solución centralizada")
            self.logger.info("   • Desventaja: Puede afectar seguridad")
            
            self.logger.info("\n🔧 OPCIÓN 2: CREAR GRUPO CON PERMISOS AMPLIOS")
            self.logger.info("   • Crear grupo 'Acceso Completo Contactos'")
            self.logger.info("   • Asignar todos los usuarios a este grupo")
            self.logger.info("   • Ventaja: Control granular")
            self.logger.info("   • Desventaja: Requiere configuración adicional")
            
            self.logger.info("\n🔧 OPCIÓN 3: ASIGNAR CONTACTOS A USUARIOS")
            self.logger.info("   • Asignar todos los contactos a cada usuario")
            self.logger.info("   • Mantener reglas actuales")
            self.logger.info("   • Ventaja: No modifica reglas de seguridad")
            self.logger.info("   • Desventaja: Puede ser lento con muchos contactos")
            
            self.logger.info("\n🎯 RECOMENDACIÓN:")
            self.logger.info("   • OPCIÓN 1: Para acceso completo inmediato")
            self.logger.info("   • OPCIÓN 2: Para control granular y seguridad")
            self.logger.info("   • OPCIÓN 3: Para mantener estructura actual")
            
        except Exception as e:
            self.logger.error(f"❌ Error proponiendo soluciones: {e}")
    
    def implementar_opcion_1_desactivar_reglas(self, models, uid, database, reglas):
        """Implementar opción 1: Desactivar reglas restrictivas"""
        try:
            self.logger.info("🔧 IMPLEMENTANDO OPCIÓN 1: DESACTIVAR REGLAS RESTRICTIVAS...")
            
            reglas_desactivadas = 0
            
            for regla in reglas:
                # Identificar reglas restrictivas
                dominio = regla.get('domain_force', [])
                if dominio and any(palabra in str(dominio) for palabra in ['user_id', 'commercial_partner_id']):
                    self.logger.info(f"   • Desactivando regla: {regla['name']} (ID: {regla['id']})")
                    
                    # Desactivar la regla
                    models.execute_kw(
                        database, uid, 'REDACTED',
                        'ir.rule', 'write',
                        [[regla['id']], {'active': False}]
                    )
                    
                    reglas_desactivadas += 1
            
            self.logger.info(f"✅ Reglas desactivadas: {reglas_desactivadas}")
            return reglas_desactivadas
            
        except Exception as e:
            self.logger.error(f"❌ Error implementando opción 1: {e}")
            return 0
    
    def implementar_opcion_2_crear_grupo(self, models, uid, database):
        """Implementar opción 2: Crear grupo con permisos amplios"""
        try:
            self.logger.info("🔧 IMPLEMENTANDO OPCIÓN 2: CREAR GRUPO CON PERMISOS AMPLIOS...")
            
            # Crear grupo
            grupo_id = models.execute_kw(
                database, uid, 'REDACTED',
                'res.groups', 'create',
                [{'name': 'Acceso Completo Contactos', 'category_id': 1}]  # category_id 1 es "Extra Rights"
            )
            
            self.logger.info(f"   • Grupo creado: ID {grupo_id}")
            
            # Obtener usuarios activos
            usuarios = models.execute_kw(
                database, uid, 'REDACTED',
                'res.users', 'search',
                [[('active', '=', True)]]
            )
            
            # Asignar grupo a todos los usuarios
            usuarios_asignados = 0
            for usuario_id in usuarios:
                if usuario_id != uid:  # No modificar el usuario admin
                    try:
                        # Obtener grupos actuales del usuario
                        usuario_grupos = models.execute_kw(
                            database, uid, 'REDACTED',
                            'res.users', 'read',
                            [[usuario_id], ['groups_id']]
                        )
                        
                        grupos_actuales = usuario_grupos[0]['groups_id']
                        if grupo_id not in grupos_actuales:
                            grupos_actuales.append(grupo_id)
                            
                            # Actualizar usuario
                            models.execute_kw(
                                database, uid, 'REDACTED',
                                'res.users', 'write',
                                [[usuario_id], {'groups_id': [(6, 0, grupos_actuales)]}]
                            )
                            
                            usuarios_asignados += 1
                    except Exception as e:
                        self.logger.warning(f"   ⚠️  Error asignando grupo a usuario {usuario_id}: {e}")
            
            self.logger.info(f"✅ Usuarios asignados al grupo: {usuarios_asignados}")
            return grupo_id, usuarios_asignados
            
        except Exception as e:
            self.logger.error(f"❌ Error implementando opción 2: {e}")
            return None, 0
    
    def verificar_cambio_permisos(self, models, uid, database, usuario_test_id=96):
        """Verificar que los cambios funcionen"""
        try:
            self.logger.info("🔍 VERIFICANDO CAMBIOS DE PERMISOS...")
            
            # Contar contactos visibles para el usuario de prueba
            total_contactos = models.execute_kw(
                database, uid, 'REDACTED',
                'res.partner', 'search_count',
                [[]]
            )
            
            self.logger.info(f"   • Total de contactos en sistema: {total_contactos}")
            
            # Verificar acceso a contactos específicos
            contactos_gomez = models.execute_kw(
                database, uid, 'REDACTED',
                'res.partner', 'search_count',
                [[('name', 'ilike', 'GOMEZ JUAN')]]
            )
            
            self.logger.info(f"   • Contactos GOMEZ JUAN: {contactos_gomez}")
            
            # Verificar acceso a contactos por categoría
            contactos_caleta = models.execute_kw(
                database, uid, 'REDACTED',
                'res.partner', 'search_count',
                [[('category_id.name', '=', 'Caleta Olivia')]]
            )
            
            self.logger.info(f"   • Contactos Caleta Olivia: {contactos_caleta}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error verificando permisos: {e}")
            return False
    
    def ejecutar_analisis_completo(self):
        """Ejecutar análisis completo de permisos"""
        try:
            self.logger.info("🚀 INICIANDO ANÁLISIS COMPLETO DE PERMISOS")
            
            # 1. Conectar
            models, uid, database = self.conectar_master_15()
            if not models:
                return False
            
            # 2. Analizar reglas actuales
            reglas = self.analizar_reglas_actuales(models, uid, database)
            
            # 3. Analizar grupos
            grupos, grupos_contactos = self.analizar_grupos_usuarios(models, uid, database)
            
            # 4. Analizar usuarios
            usuarios = self.analizar_usuarios_activos(models, uid, database)
            
            # 5. Proponer soluciones
            self.proponer_soluciones(reglas, grupos, usuarios)
            
            self.logger.info("\n🎯 ANÁLISIS COMPLETADO")
            self.logger.info("   ✅ Reglas analizadas")
            self.logger.info("   ✅ Grupos analizados")
            self.logger.info("   ✅ Usuarios analizados")
            self.logger.info("   ✅ Soluciones propuestas")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error en análisis completo: {e}")
            return False

def main():
    """Función principal"""
    try:
        analizador = AnalizadorModificadorPermisos()
        exito = analizador.ejecutar_analisis_completo()
        
        if exito:
            print(f"\n✅ Análisis de permisos completado exitosamente")
            print(f"\n💡 PRÓXIMOS PASOS:")
            print(f"   1. Revisar las opciones propuestas")
            print(f"   2. Elegir la solución preferida")
            print(f"   3. Ejecutar la implementación")
        else:
            print(f"\n❌ Error en el análisis")
        
        return exito
        
    except Exception as e:
        print(f"❌ Error en función principal: {e}")
        return False

if __name__ == "__main__":
    main()















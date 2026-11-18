# Cómo contribuir

Normas de Git del grupo (commits de control, fechas y contenido en el documento *Seguimiento y control de versiones PBL Redes*).

- **Ramas.** `main` solo recibe fusiones por pull request. Una rama por tarea: `pbl1/1.3-servidor`, `pbl1/1.2-pki`...
- **Mensajes.** `tipo(ID): descripción`, con `feat`, `fix`, `docs`, `test` o `chore`; el ID es la tarea del reparto. Ejemplo: `feat(1.3): servidor reenvía el ciclo completo`. Plantilla activable con `git config commit.template .gitmessage`.
- **Ritmo.** Un commit por persona y semana como mínimo, y un commit de control cada lunes y jueves a las 20:00.
- **Revisión.** Cada pull request lo revisan los otros tres compañeros: todos deben entender todo el código. Cada revisor deja una frase con lo que entiende que hace y una duda. Se fusiona cuando el revisor principal aprueba y los otros dos lo han leído y comentado.
- **Etiquetas.** `h1`, `h2`, `h3` tras cada seguimiento y `v1.0` en la entrega.
- **Nunca en el repositorio:** claves privadas, contraseñas ni `.env`. La configuración real va en ficheros ignorados; solo se versiona el ejemplo.

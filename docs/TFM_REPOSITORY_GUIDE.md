# Guía académica del repositorio Classio

Classio es una plataforma de apoyo a la planificación docente, creación de materiales y seguimiento del aprendizaje. El TFM estudia tres cuestiones: si reduce el tiempo de trabajo con calidad equivalente (OE1), si sus recomendaciones son más pertinentes que un baseline de reglas (OE2), y si una evolución modular con Expo y servicios Python es viable técnica y económicamente (OE3). **Esos objetivos son hipótesis de evaluación, no resultados demostrados por la existencia del código.**

Esta guía pertenece a la [auditoría académica](TFM_TECHNICAL_AUDIT.md). El [registro único](AUDITORIAS_ESTADO_2026-10-22.md) separa sus afirmaciones de las auditorías financiera, tecnológica y de paridad.

## Cómo leer el repositorio

| Ruta | Contenido | Madurez |
| --- | --- | --- |
| `streamlit/` | Aplicación Python existente: gestión, materiales, recomendaciones, pruebas y experimentos | Implementación operativa con pruebas de unidad; aceptación y efecto académico por evaluar |
| `expo/` | Cliente React Native/web en migración, con flujos de docentes y estudiantes | Implementación parcial; paridad y aceptación pendientes |
| `python_api/` | API autenticada para inferencia y otras operaciones protegidas | Integración condicionada a Supabase y modelos aprobados |
| `.github/workflows/tests.yml` | Compilación, pruebas Python, instalación y verificaciones Expo | La ejecución 39434508082 de `ef1713ec` pasó Streamlit y falló Expo antes de sus verificaciones; el estado de CI del corte actual no está acreditado aquí |
| `streamlit/reports/ml_architecture/` | Resúmenes, informes y algunos artefactos de experimentos | Evidencia histórica exploratoria; los CSV privados por fila no están en Git |
| `docs/TFM_TECHNICAL_AUDIT.md` | Matriz de afirmaciones, código, evidencia y límites | Punto de partida para auditar afirmaciones |
| `docs/TFM_ML_REPRODUCIBILITY.md` | Fuentes, particiones, artefactos y protocolo de ablación | Método reproducible sujeto a acceso autorizado a datos |

## Tecnología e IA

Streamlit y Python sostienen la aplicación existente. Expo/React Native con TypeScript ofrece una superficie móvil y web. Ambas aplicaciones dependen de Supabase para identidad y datos; Expo usa claves públicas y políticas de acceso, mientras que `python_api/` conserva operaciones que necesitan verificación de identidad y artefactos privados. Se usa IA generativa para ayudar a preparar contenidos; su salida requiere revisión docente. El ML sirve para ordenar recursos con señales de contexto y comportamiento, y para explorar afinidad semántica. Ni la generación automática ni un mejor valor de similitud prueban por sí mismos mejora del aprendizaje.

Los experimentos principales son la **predicción supervisada** de apertura de una recomendación en siete días y la **afinidad no supervisada** entre perfiles de recursos y temas curriculares. El primero es offline y no alimenta el ranking actual. El segundo dispone de una ruta de inferencia aprobada condicionalmente, pero faltan juicios humanos independientes para medir pertinencia. Véase [reproducibilidad](TFM_ML_REPRODUCIBILITY.md).

## Pruebas reproducibles sin datos reales

```bash
cd streamlit
python -m pip install --requirement requirements.lock.txt
python -m compileall -q app.py app_pages auth core helpers services styles
python scripts/check_migrations.py
python -m unittest discover -s tests

cd ../expo
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run lint
pnpm run export:web

cd ..
python -m unittest discover -s scripts -p 'test_tfm_*.py'
```

Para la API, instalar `python_api/requirements.txt` en un entorno aislado y ejecutar sus pruebas desde la raíz con `PYTHONPATH=streamlit:.`. No hacen falta credenciales para los tests aislados. Ejecutar los experimentos reales exige permisos y datasets privados; las pruebas sintéticas no son evidencia de rendimiento.

## Límites de la primera entrega

La matriz técnica distingue capacidades implementadas, ensayadas solo con pruebas unitarias y exploratorias. Faltan mediciones controladas de OE1, juicios independientes y ablación comparable para OE2, y análisis de coste total y validación de flujos críticos para OE3. La segunda entrega desarrollará el diseño arquitectónico: contratos entre Expo, API Python y Supabase, seguridad, despliegue, observabilidad, resiliencia y coste de operación. Esta primera entrega documenta el problema y el planteamiento tecnológico sin presentar ese diseño como terminado.

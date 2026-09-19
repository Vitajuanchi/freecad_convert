# Animación editorial del metegol

Escenario de fondo blanco con iluminación editorial y una animación de cámara
de 10 segundos, listos para correr sobre el `.blend` del metegol.

## Qué arma el script

- **Ciclorama cerrado de 360°**: piso y pared unidos por un empalme curvo y
  revolucionados alrededor del sujeto. No hay línea de horizonte ni borde del
  fondo, así que la cámara puede dar la vuelta completa.
- **Esquema de luces de producto**: key suave grande adelante a la izquierda,
  fill amplio del lado opuesto, rim atrás para separar del fondo y cenital
  para los brillos largos sobre las superficies horizontales. Las posiciones y
  potencias son múltiplos del tamaño del sujeto, así que el esquema se adapta
  solo a cualquier modelo.
- **Cámara con encuadre calculado**: para cada keyframe, el script resuelve
  numéricamente a qué distancia poner la cámara para que el metegol ocupe la
  fracción de cuadro pedida. No hay distancias hardcodeadas: funciona igual con
  un modelo chico o grande.

## Animación (10 s, 25 fps, 250 frames)

| Frame | t | Órbita | Altura | Encuadre | Lente |
|-------|------|--------|--------|----------|-------|
| 1   | 0,0 s  | -40°  | 1,80 × alto | 68 % | 45 mm |
| 63  | 2,5 s  | 15°   | 1,38 × alto | 80 % | 52 mm |
| 125 | 5,0 s  | 115°  | 1,22 × alto | 88 % | 58 mm |
| 188 | 7,5 s  | 225°  | 1,55 × alto | 72 % | 55 mm |
| 250 | 10,0 s | 320°  | 1,40 × alto | 82 % | 62 mm |

Es una órbita continua de 360° con un acercamiento progresivo: abre alto y
abierto, baja y se acerca hasta el perfil, sube y abre por detrás, y cierra en
el plano héroe. Todas las curvas son Bézier con handles automáticos y easing en
los extremos, así que arranca y frena suave, sin tirones.

## Uso

```bash
# 1. Prueba rápida: 5 frames sueltos a media resolución, para revisar encuadre y luz
blender metegol.blend --background --python studio_animation.py -- \
    --out preview --test

# 2. Render completo de los 10 s (secuencia PNG)
blender metegol.blend --background --python studio_animation.py -- \
    --out render --samples 48

# 3. Armar el MP4
blender --background --python encode_video.py -- \
    --frames render --out metegol_10s.mp4 --fps 25
```

El render sale como secuencia PNG y no como MP4 directo a propósito: si el
render se corta, los frames ya hechos se conservan y se puede retomar.

### Opciones

| Opción | Default | Para qué |
|--------|---------|----------|
| `--out` | `render` | carpeta de salida de los PNG |
| `--duration` | `10` | duración en segundos |
| `--fps` | `25` | cuadros por segundo |
| `--res` | `1920x1080` | resolución |
| `--samples` | `64` | samples de Cycles |
| `--size` | `2.2` | tamaño al que se normaliza el metegol, en metros |
| `--exposure` | `0` | corrección de exposición en pasos |
| `--test` | — | 5 frames sueltos a media resolución |
| `--save-blend` | — | guarda el `.blend` con escenario y keyframes armados |
| `--no-dof` | — | desactiva la profundidad de campo |
| `--no-render` | — | arma todo pero no renderiza |

Si el metegol queda sobreexpuesto o apagado, `--exposure` es la perilla más
directa: `--exposure -0.4` lo baja, `--exposure 0.3` lo sube.

## Qué le hace el script al archivo

El script **no pisa el `.blend` original** salvo que se use `--save-blend`.
Sobre la escena cargada:

1. Borra las cámaras y luces que haya (el escenario aporta las suyas).
2. Agrupa toda la geometría bajo un empty `METEGOL_ROOT`.
3. Centra el modelo en el origen, lo apoya sobre el piso y lo escala a `--size`.
4. Agrega el ciclorama, las luces y la cámara, todo con el prefijo `STUDIO_`.

Los materiales del modelo se respetan tal como están.

## Render

Cycles en CPU, con denoiser OpenImageDenoise y sampling adaptativo. El
*view transform* es `Standard` y no AgX: AgX desatura y agrisa los blancos, y
acá el fondo tiene que leer blanco limpio.

`use_persistent_data` queda activado, que es lo que más acelera una animación
en CPU: reusa la escena traducida entre frames en lugar de rearmarla en cada
uno.

## Archivos

- `studio_animation.py` — arma el escenario, las luces, la cámara y los keyframes.
- `encode_video.py` — junta la secuencia PNG en un MP4.
- `make_proxy_metegol.py` — genera un metegol de prueba, para validar encuadre e
  iluminación sin el modelo real.

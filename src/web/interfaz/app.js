/* Interfaz web de la celda (tarea 1.7).
 * JS sin librerías + SVG en línea. Sondea GET /api/robot y dibuja el robot en dos
 * vistas ortogonales 2D (superior = X/Y, frontal = X/Z) a partir de una misma pose 3D.
 *
 * La pose se *deduce del estado del ciclo* (cada estado corresponde a una estación).
 * Más adelante puede venir de la posición real (campo `position` de ROBOT_STATUS,
 * docs/contratos.md): solo cambia ponerDestino().
 *
 * Opciones en la URL:  ?movimiento=0  -> sin interpolación, el robot salta entre estaciones
 */
(function () {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var SONDEO_MS = 200;
  var MOVIMIENTO = !/[?&]movimiento=0/.test(location.search);
  var MS_TRASLADO = 1000;     // tiempo visual de traslado entre estaciones
  var MS_GIRO = 450;          // tiempo visual del giro de la pieza
  var ELEVACION = 140;        // mm que sube el brazo durante el traslado (visual)
  var PASO_GIRO = 15;         // grados por giro del eje 6 (docs/variables-krl.md)
  var ESTADOS_DESTELLO = [2]; // estados en los que parpadea la cámara (pide imágenes)

  // ---- geometría de la celda (mm, base del robot en el origen; X derecha, Y al fondo, Z arriba)
  var G = { hombroZ: 190, l1: 270, l2: 250 };
  var EST = {
    cinta:  { yaw: 180, r: 380, z: 80 },
    camara: { yaw: 0,   r: 330, z: 330 },
    buena:  { yaw: -55, r: 390, z: 110 },
    mala:   { yaw: -125, r: 390, z: 110 }
  };
  var POSE_DE_ESTADO = { 0: 'cinta', 1: 'camara', 2: 'camara', 3: 'buena', 4: 'mala' };
  var D2R = Math.PI / 180;

  function xyEstacion(s) { return { x: s.r * Math.cos(s.yaw * D2R), y: s.r * Math.sin(s.yaw * D2R) }; }
  var PILA = { buena: xyEstacion(EST.buena), mala: xyEstacion(EST.mala) };
  var RECOGIDA = xyEstacion(EST.cinta);

  // ---- utilidades
  function $(id) { return document.getElementById(id); }
  function el(tag, attrs, padre) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (padre) padre.appendChild(e);
    return e;
  }
  function texto(padre, x, y, s, cls, extra) {
    var t = el('text', Object.assign({ x: x, y: y, class: cls || 'label', 'text-anchor': 'middle' }, extra || {}), padre);
    t.textContent = s;
    return t;
  }
  function limitar(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function suavizar(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }
  function hora(ts) { return new Date(ts * 1000).toLocaleTimeString([], { hour12: false }); }
  function escapar(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  function rejilla(svg, x0, y0, w, h) {
    var g = el('g', {}, svg);
    for (var x = Math.ceil(x0 / 100) * 100; x <= x0 + w; x += 100) el('line', { x1: x, y1: y0, x2: x, y2: y0 + h, class: 'grid-line' }, g);
    for (var y = Math.ceil(y0 / 100) * 100; y <= y0 + h; y += 100) el('line', { x1: x0, y1: y, x2: x0 + w, y2: y, class: 'grid-line' }, g);
  }

  // ---- robot (misma estructura en las dos vistas)
  function crearRobot(svg) {
    var g = el('g', { class: 'robot' }, svg);
    var r = {
      g: g,
      l1: el('line', { class: 'link' }, g),
      l2: el('line', { class: 'link-2' }, g),
      j0: el('circle', { r: 18, class: 'joint' }, g),
      j1: el('circle', { r: 15, class: 'joint' }, g),
      pieza: el('g', {}, g)
    };
    r.cuerpoPieza = el('rect', { x: -26, y: -26, width: 52, height: 52, rx: 4, class: 'part' }, r.pieza);
    r.marcaPieza = el('line', { x1: 0, y1: 0, x2: 0, y2: -22, class: 'part-mark' }, r.pieza);
    r.brida = el('circle', { r: 10, class: 'joint' }, g);
    return r;
  }

  // ---- escenas fijas
  var sup = {}, fro = {};

  function crearCamara(svg, cy, vista) {
    var g = el('g', { class: 'camera' }, svg);
    var abre = vista === 'superior' ? 80 : 70;
    el('polygon', { points: '592,' + (cy - 10) + ' 592,' + (cy + 10) + ' 300,' + (cy + abre) + ' 300,' + (cy - abre), class: 'cam-fov' }, g);
    if (vista === 'frontal') {
      el('rect', { x: 641, y: cy + 30, width: 18, height: -cy - 30, class: 'equip' }, g);
      el('rect', { x: 600, y: -12, width: 100, height: 12, class: 'equip' }, g);
    }
    el('rect', { x: 610, y: cy - 32, width: 82, height: 64, rx: 6, class: 'cam-body' }, g);
    el('circle', { cx: 604, cy: cy, r: 18, class: 'cam-lens' }, g);
    el('circle', { cx: 676, cy: cy - 18, r: 6, class: 'cam-led' }, g);
    return g;
  }

  function crearSuperior() {
    var svg = $('vistaSuperior');
    rejilla(svg, -2400, -1200, 4800, 2400);
    el('circle', { cx: 0, cy: 0, r: G.l1 + G.l2, class: 'reach' }, svg);

    // cinta (avanza hacia el punto de recogida)
    el('rect', { x: -460, y: -700, width: 160, height: 1400, class: 'belt' }, svg);
    for (var y = -540; y <= 680; y += 120) {
      el('path', { d: 'M -415 ' + (y + 18) + ' L -380 ' + (y - 12) + ' L -345 ' + (y + 18), class: 'belt-mark' }, svg);
    }
    texto(svg, -505, 0, 'CINTA', 'label', { transform: 'rotate(-90 -505 0)' });

    // pilas
    ['buena', 'mala'].forEach(function (k) {
      var p = PILA[k], cls = k === 'buena' ? 'ok' : 'nok';
      el('rect', { x: p.x - 80, y: -p.y - 80, width: 160, height: 160, rx: 6, class: 'equip bin ' + cls }, svg);
      sup['cuenta_' + k] = texto(svg, p.x, -p.y + 18, '0', 'bin-count ' + cls);
      texto(svg, p.x, -p.y + 125, k === 'buena' ? 'PILA OK' : 'PILA RECHAZO');
    });

    sup.camara = crearCamara(svg, 0, 'superior');
    texto(svg, 650, 75, 'CÁMARA');

    sup.esperando = el('rect', { x: RECOGIDA.x - 26, y: -RECOGIDA.y - 26, width: 52, height: 52, rx: 4, class: 'part' }, svg);
    el('circle', { cx: 0, cy: 0, r: 72, class: 'robot-base' }, svg);
    sup.robot = crearRobot(svg);
  }

  function crearFrontal() {
    var svg = $('vistaFrontal');
    rejilla(svg, -2400, -1400, 4800, 1480);
    el('line', { x1: -2400, y1: 0, x2: 2400, y2: 0, class: 'floor' }, svg);

    // cinta vista de lado
    el('rect', { x: -450, y: -48, width: 14, height: 48, class: 'equip' }, svg);
    el('rect', { x: -324, y: -48, width: 14, height: 48, class: 'equip' }, svg);
    el('rect', { x: -470, y: -60, width: 180, height: 16, rx: 8, class: 'belt' }, svg);
    texto(svg, -380, 50, 'CINTA', 'label-sm');

    // pilas con piezas apiladas
    ['buena', 'mala'].forEach(function (k) {
      var p = PILA[k], cls = k === 'buena' ? 'ok' : 'nok';
      fro['pila_' + k] = el('g', {}, svg);
      el('path', { d: 'M ' + (p.x - 80) + ' -90 L ' + (p.x - 80) + ' 0 L ' + (p.x + 80) + ' 0 L ' + (p.x + 80) + ' -90', class: 'equip bin ' + cls, fill: 'none' }, svg);
      texto(svg, p.x, 50, k === 'buena' ? 'OK' : 'RECHAZO', 'label-sm');
    });

    fro.camara = crearCamara(svg, -EST.camara.z, 'frontal');
    fro.textoCamara = texto(svg, 650, -EST.camara.z - 60, '', 'label-sm');
    texto(svg, 650, 50, 'CÁMARA', 'label-sm');

    // base y columna del robot
    el('path', { d: 'M -78 0 L -52 -110 L 52 -110 L 78 0 Z', class: 'robot-base' }, svg);
    el('rect', { x: -32, y: -G.hombroZ, width: 64, height: G.hombroZ - 110, class: 'robot-base' }, svg);
    fro.esperando = el('rect', { x: RECOGIDA.x - 26, y: -EST.cinta.z - 26, width: 52, height: 52, rx: 4, class: 'part' }, svg);
    fro.robot = crearRobot(svg);
  }

  // ---- cinemática: (yaw, r, z) -> codo y muñeca en 3D (2 eslabones, codo arriba)
  function resolver(p) {
    var yaw = p.yaw * D2R, r = p.r, h = p.z - G.hombroZ;
    var d = Math.hypot(r, h), dmax = G.l1 + G.l2 - 1;
    if (d > dmax) { r *= dmax / d; h *= dmax / d; d = dmax; }
    var a = Math.atan2(h, r);
    var b = Math.acos(limitar((G.l1 * G.l1 + d * d - G.l2 * G.l2) / (2 * G.l1 * d), -1, 1));
    var er = G.l1 * Math.cos(a + b), eh = G.l1 * Math.sin(a + b);
    var c = Math.cos(yaw), s = Math.sin(yaw);
    return {
      codo: { x: er * c, y: er * s, z: G.hombroZ + eh },
      muneca: { x: r * c, y: r * s, z: G.hombroZ + h }
    };
  }

  function linea(l, x1, y1, x2, y2) { l.setAttribute('x1', x1); l.setAttribute('y1', y1); l.setAttribute('x2', x2); l.setAttribute('y2', y2); }
  function centro(c, x, y) { c.setAttribute('cx', x); c.setAttribute('cy', y); }

  function dibujarRobot(R, k, proyectar, anguloPieza) {
    var s = proyectar({ x: 0, y: 0, z: G.hombroZ }), e = proyectar(k.codo), w = proyectar(k.muneca);
    linea(R.l1, s[0], s[1], e[0], e[1]);
    linea(R.l2, e[0], e[1], w[0], w[1]);
    centro(R.j0, s[0], s[1]); centro(R.j1, e[0], e[1]); centro(R.brida, w[0], w[1]);
    R.pieza.setAttribute('transform', 'translate(' + w[0].toFixed(1) + ' ' + w[1].toFixed(1) + ') rotate(' + anguloPieza.toFixed(1) + ')');
  }
  var proySuperior = function (p) { return [p.x, -p.y]; };
  var proyFrontal = function (p) { return [p.x, -p.z]; };

  // ---- animación
  var pose = Object.assign({}, EST.cinta), desde = pose, hacia = pose, t0 = 0, moviendo = false;
  var giro = 0, giroDesde = 0, giroHacia = 0, g0 = 0;
  var idFrame = 0;
  var vista = { estado: null };
  var primeraVez = true;

  function ponerDestino(nombre, saltar) {
    var destino = EST[nombre];
    if (hacia === destino && !saltar) return;
    desde = Object.assign({}, pose); hacia = destino;
    if (saltar || !MOVIMIENTO) { pose = Object.assign({}, destino); moviendo = false; }
    else { t0 = performance.now(); moviendo = true; }
    pedirFrame();
  }
  function ponerGiro(grados, saltar) {
    giroDesde = giro; giroHacia = grados;
    if (saltar || !MOVIMIENTO) giro = grados; else g0 = performance.now();
    pedirFrame();
  }
  function pedirFrame() { if (!idFrame) idFrame = requestAnimationFrame(frame); }

  function frame(ahora) {
    idFrame = 0;
    if (moviendo) {
      var t = limitar((ahora - t0) / MS_TRASLADO, 0, 1), e = suavizar(t);
      var dyaw = ((hacia.yaw - desde.yaw + 540) % 360) - 180;
      var arco = Math.sin(Math.PI * e);
      pose = {
        yaw: desde.yaw + dyaw * e,
        r: desde.r + (hacia.r - desde.r) * e - 70 * arco,
        z: desde.z + (hacia.z - desde.z) * e + ELEVACION * arco
      };
      if (t >= 1) { moviendo = false; pose = Object.assign({}, hacia); }
    }
    if (giro !== giroHacia) {
      var tg = limitar((ahora - g0) / MS_GIRO, 0, 1);
      giro = giroDesde + (giroHacia - giroDesde) * suavizar(tg);
      if (tg >= 1) giro = giroHacia;
    }
    pintar();
    if (moviendo || giro !== giroHacia) pedirFrame();
  }

  function pintar() {
    var k = resolver(pose);
    // en el estado 0 la pinza va vacía a la cinta y allí coge la pieza que espera
    var conPieza = !(vista.estado === 0 && moviendo);
    var cls = 'part' + (vista.estado === 3 ? ' ok' : vista.estado === 4 ? ' nok' : '');
    [sup, fro].forEach(function (v) {
      v.robot.pieza.style.display = conPieza ? '' : 'none';
      v.esperando.style.display = conPieza ? 'none' : '';
      v.robot.cuerpoPieza.setAttribute('class', cls);
    });
    dibujarRobot(sup.robot, k, proySuperior, -pose.yaw);
    dibujarRobot(fro.robot, k, proyFrontal, giro);
  }

  // ---- actualización con los datos del servidor
  var ultimaClaveEventos = '', ultimaPila = { buena: -1, mala: -1 };

  function insignia(id, cls) { $(id).className = 'badge ' + cls; }

  function dibujarPila(k, n) {
    if (ultimaPila[k] === n) return;
    ultimaPila[k] = n;
    var g = fro['pila_' + k], p = PILA[k], cls = k === 'buena' ? 'ok' : 'nok';
    while (g.firstChild) g.removeChild(g.firstChild);
    for (var i = 0; i < Math.min(n, 5); i++) {
      el('rect', { x: p.x - 29 + (i % 2) * 6, y: -16 - i * 15, width: 52, height: 14, rx: 2, class: 'stack ' + cls }, g);
    }
    sup['cuenta_' + k].textContent = n;
  }

  function actualizar(d) {
    $('celda').textContent = d.celda;
    $('robot').textContent = (d.robot || 'Robot') + ' · Inspección por visión';
    $('variable').textContent = d.variable;
    $('pOrigen').textContent = d.origen;
    $('pVariable').textContent = d.variable;
    $('pValor').textContent = d.valor_bruto === null ? '—' : d.valor_bruto;
    $('pPeriodo').textContent = d.periodo_ms + ' ms';
    $('pLectura').textContent = d.ms_lectura === null ? '—' : d.ms_lectura + ' ms';

    var im = $('insModo');
    im.textContent = d.modo === 'kvp' ? 'ROBOT REAL' : d.modo === 'escenario' ? 'ESCENARIO' : 'SIMULACIÓN';
    im.className = 'badge' + (d.modo === 'kvp' ? '' : ' sim');
    insignia('insWeb', 'good');
    insignia('insRobot', d.conectado ? 'good' : 'bad');

    var s = d.conectado ? d.estado : null;
    var sinDatos = s === null || s === undefined;

    var al = $('alarma');
    if (!d.conectado) { al.hidden = false; al.textContent = 'ENLACE CON EL ROBOT CAÍDO — ' + (d.ultimo_error || 'KukaVarProxy no responde'); }
    else if (sinDatos) { al.hidden = false; al.textContent = 'VALOR DE ESTADO NO VÁLIDO — ' + d.ultimo_error; }
    else al.hidden = true;

    // transiciones de estado -> destinos visuales
    if (!sinDatos && s !== vista.estado) {
      var primero = vista.estado === null;
      vista.estado = s;
      ponerDestino(POSE_DE_ESTADO[s], primero);
    }
    // ángulo de la pieza = giros del ciclo × 15° (lo cuenta el servidor: igual en todos los navegadores)
    if (!sinDatos && d.giros * PASO_GIRO !== giroHacia) ponerGiro(d.giros * PASO_GIRO, s === 0 || primeraVez);
    primeraVez = false;
    document.body.classList.toggle('nodata', sinDatos);
    [sup.camara, fro.camara].forEach(function (c) {
      c.classList.toggle('armed', !sinDatos && (s === 1 || s === 2));
      c.classList.toggle('flash', !sinDatos && ESTADOS_DESTELLO.indexOf(s) >= 0);
    });
    fro.textoCamara.textContent = (!sinDatos && (s === 1 || s === 2)) ? 'GIRO ' + (giroHacia % 360) + '°  ·  #' + d.giros : '';
    if (sinDatos) pintar();

    // tarjeta de estado
    $('tarjetaEstado').className = 'panel state-card ' + (sinDatos ? 'nodata' : 's' + s);
    $('valorEstado').textContent = sinDatos ? '–' : s;
    $('nombreEstado').textContent = d.conectado ? d.nombre_estado : 'SIN DATOS';
    $('tiempoEstado').textContent = d.segundos_en_estado.toFixed(1) + ' s';
    $('numGiros').textContent = '×' + d.giros;
    var lis = $('pasos').children;
    for (var i = 0; i < lis.length; i++) lis[i].classList.toggle('active', !sinDatos && +lis[i].dataset.s === s);

    // indicadores
    var c = d.contadores, total = c.buenas + c.malas;
    $('kCiclos').textContent = c.ciclos;
    $('kBuenas').textContent = c.buenas;
    $('kMalas').textContent = c.malas;
    $('kRend').textContent = total ? (100 * c.buenas / total).toFixed(1) + ' %' : '– %';
    $('kUltimo').textContent = d.ultimo_ciclo_s ? d.ultimo_ciclo_s.toFixed(1) + ' s' : '– s';
    $('kActual').textContent = d.segundos_ciclo ? d.segundos_ciclo.toFixed(1) + ' s' : '– s';
    dibujarPila('buena', c.buenas);
    dibujarPila('mala', c.malas);

    // eventos (solo se repintan si cambian)
    var clave = d.eventos.length ? d.eventos[0].t + '|' + d.eventos.length : '';
    if (clave !== ultimaClaveEventos) {
      ultimaClaveEventos = clave;
      $('eventos').innerHTML = d.eventos.map(function (e) {
        return '<li class="' + e.nivel + '"><time>' + hora(e.t) + '</time><span>' + escapar(e.texto) + '</span></li>';
      }).join('');
      $('numEventos').textContent = d.eventos.length + ' últimos';
    }
  }

  function sinEnlaceWeb() {
    insignia('insWeb', 'bad');
    insignia('insRobot', '');
    var al = $('alarma');
    al.hidden = false;
    al.textContent = 'SERVIDOR WEB NO DISPONIBLE — los datos no están actualizados';
    document.body.classList.add('nodata');
    [sup.camara, fro.camara].forEach(function (c) { c.classList.remove('armed', 'flash'); });
  }

  // ---- bucle de sondeo (nunca se solapa; límite de 1,5 s por petición)
  function sondear() {
    var ctl = window.AbortController ? new AbortController() : null;
    var tm = setTimeout(function () { if (ctl) ctl.abort(); }, 1500);
    fetch('/api/robot', { cache: 'no-store', signal: ctl ? ctl.signal : undefined })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(actualizar)
      .catch(sinEnlaceWeb)
      .then(function () { clearTimeout(tm); setTimeout(sondear, SONDEO_MS); });
  }

  // ---- resto de la interfaz
  function reloj() { $('reloj').textContent = new Date().toLocaleTimeString([], { hour12: false }); }

  function iniciarTema() {
    var guardado = localStorage.getItem('tema-web');
    if (guardado) document.documentElement.dataset.theme = guardado;
    $('btnTema').addEventListener('click', function () {
      var t = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      document.documentElement.dataset.theme = t;
      localStorage.setItem('tema-web', t);
    });
  }

  $('btnReiniciar').addEventListener('click', function () {
    if (confirm('¿Reiniciar los contadores de producción?')) fetch('/api/contadores/reiniciar', { method: 'POST' });
  });

  iniciarTema();
  crearSuperior();
  crearFrontal();
  pintar();
  reloj();
  setInterval(reloj, 1000);
  sondear();
})();

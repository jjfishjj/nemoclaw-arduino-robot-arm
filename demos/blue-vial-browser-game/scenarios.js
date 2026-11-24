(() => {
  'use strict';

  const runtime = window.BlueVialRuntime;
  if (!runtime) throw new Error('Blue Vial runtime was not initialized');

  const { THREE, scene } = runtime;
  const $ = id => document.getElementById(id);
  const SCENARIO_RUN_SECONDS = 4;
  const blueStepHtml = $('steps').innerHTML;
  const sharedSceneObjects = new Set([runtime.amb, runtime.key, runtime.rim, runtime.floor, runtime.grid]);
  const blueSceneObjects = scene.children.filter(object => !sharedSceneObjects.has(object));

  const style = document.createElement('style');
  style.textContent = `
    .scenario-picker{display:block;margin:0 0 9px}
    .scenario-picker span{display:block;margin-bottom:5px;color:#819398;font:700 9px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.12em;text-transform:uppercase}
    .scenario-picker select{width:100%;border:1px solid #294548;border-radius:5px;background:#0a1518;color:#dceaea;padding:8px 9px;font:600 10px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
    .scenario-scope{margin-top:5px;color:#ba9c7a;font:8px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.04em}
    .target-icon.scenario-delivery{border-color:#d9b462;background:linear-gradient(145deg,#e7bd66dd,#74501aaa 58%,#302416);box-shadow:inset 3px 0 7px #fff1bb44,0 0 15px #e0a73333}
    .target-icon.scenario-laser{border-color:#8d8bff;background:linear-gradient(145deg,#c9d9e9,#567487 58%,#182b43);box-shadow:inset 3px 0 7px #e1f3ff55,0 0 15px #8a92ff33}
    @media(max-width:820px){.scenario-picker{margin-bottom:7px}}
  `;
  document.head.appendChild(style);

  const missionSection = document.querySelector('.side.left .section');
  const scenarioPicker = document.createElement('label');
  scenarioPicker.className = 'scenario-picker';
  scenarioPicker.innerHTML = `
    <span>任務情境 / MOCK SCENARIOS</span>
    <select id="scenarioSelect" aria-label="選擇機器人模擬情境">
      <option value="blue-vial">Blue Vial · 藥瓶抓取</option>
      <option value="delivery">餐飲配送 · 送餐機器人</option>
      <option value="laser-coating">半導體實驗室 · 雷射鍍膜</option>
    </select>
    <div class="scenario-scope">BROWSER MOCK ONLY · NO HARDWARE / NO PROCESS</div>
  `;
  missionSection.insertBefore(scenarioPicker, missionSection.querySelector('.taskbox'));

  document.querySelector('.brandmark').textContent = 'RS';
  document.querySelector('.brand-title').textContent = 'ROBOT SCENARIO LAB';
  document.querySelector('.brand-sub').textContent = 'BLUE VIAL · DELIVERY · LAB PROCESS MOCK';
  document.title = 'Robot Scenario Lab — Browser Mock Simulations';
  const scenarioSelect = $('scenarioSelect');
  const bbox = $('bbox');
  const maskLabel = $('maskLabel');
  const viewport = $('viewport');
  const deliveryGroup = new THREE.Group();
  deliveryGroup.name = 'delivery_mock_scene';
  scene.add(deliveryGroup);
  const labGroup = new THREE.Group();
  labGroup.name = 'laser_coating_mock_scene';
  scene.add(labGroup);
  deliveryGroup.visible = false;
  labGroup.visible = false;

  function makeMaterial(color, roughness = 0.58, metalness = 0, extra = {}) {
    return new THREE.MeshStandardMaterial({ color, roughness, metalness, ...extra });
  }

  function addBox(parent, width, height, depth, color, x, y, z, extra = {}) {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(width, height, depth),
      makeMaterial(color, extra.roughness ?? 0.58, extra.metalness ?? 0, extra.material ?? {}),
    );
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  function addCylinder(parent, radiusTop, radiusBottom, height, color, x, y, z, extra = {}) {
    const mesh = new THREE.Mesh(
      new THREE.CylinderGeometry(radiusTop, radiusBottom, height, extra.segments ?? 24),
      makeMaterial(color, extra.roughness ?? 0.55, extra.metalness ?? 0, extra.material ?? {}),
    );
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }

  function addDeliveryScene() {
    addBox(deliveryGroup, 4.6, 0.018, 0.07, 0x287b70, 0, 0.015, 1.42);
    addBox(deliveryGroup, 4.6, 0.018, 0.07, 0x287b70, 0, 0.015, -1.42);
    for (const x of [-1.5, -0.5, 0.5, 1.5]) {
      addBox(deliveryGroup, 0.035, 0.012, 0.22, 0x4cb8a1, x, 0.02, 1.42);
      addBox(deliveryGroup, 0.035, 0.012, 0.22, 0x4cb8a1, x, 0.02, -1.42);
    }

    const routePoints = [
      new THREE.Vector3(-1.68, 0.035, 0.78),
      new THREE.Vector3(-0.78, 0.035, 0.78),
      new THREE.Vector3(-0.12, 0.035, 0.18),
      new THREE.Vector3(0.58, 0.035, -0.38),
      new THREE.Vector3(1.12, 0.035, -0.54),
    ];
    const route = new THREE.Line(
      new THREE.BufferGeometry().setFromPoints(routePoints),
      new THREE.LineDashedMaterial({ color: 0x64e1bd, dashSize: 0.14, gapSize: 0.09, transparent: true, opacity: 0.85 }),
    );
    route.computeLineDistances();
    deliveryGroup.add(route);

    // A small fixed bollard makes the navigation mock visibly route around an obstacle.
    addCylinder(deliveryGroup, 0.13, 0.17, 0.32, 0xd89444, 0.08, 0.18, 0.44, { segments: 20 });
    addCylinder(deliveryGroup, 0.14, 0.14, 0.05, 0xffd08a, 0.08, 0.36, 0.44, { segments: 20 });

    const tableX = 1.23;
    const tableZ = -0.6;
    addBox(deliveryGroup, 1.02, 0.12, 0.82, 0x35595c, tableX, 0.72, tableZ, { metalness: 0.12 });
    for (const x of [tableX - 0.42, tableX + 0.42]) {
      for (const z of [tableZ - 0.31, tableZ + 0.31]) {
        addBox(deliveryGroup, 0.07, 0.58, 0.07, 0x253c3f, x, 0.39, z, { metalness: 0.2 });
      }
    }
    addBox(deliveryGroup, 0.38, 0.025, 0.32, 0x1d6d5d, tableX, 0.795, tableZ, { roughness: 0.34 });
    addBox(deliveryGroup, 0.25, 0.16, 0.22, 0xd7b66f, tableX - 0.04, 0.89, tableZ, { roughness: 0.42 });

    const robot = new THREE.Group();
    robot.name = 'mock_food_delivery_robot';
    const chassis = addBox(robot, 0.88, 0.25, 0.68, 0x2c7770, 0, 0.35, 0, { metalness: 0.22, roughness: 0.38 });
    chassis.material.emissive = new THREE.Color(0x082c27);
    addBox(robot, 0.78, 0.08, 0.08, 0x9de4c4, 0, 0.34, 0.36, { roughness: 0.28 });
    for (const x of [-0.43, 0.43]) {
      for (const z of [-0.28, 0.28]) {
        const wheel = addCylinder(robot, 0.15, 0.15, 0.12, 0x182325, x, 0.18, z, { segments: 18, roughness: 0.7 });
        wheel.rotation.z = Math.PI / 2;
        addCylinder(robot, 0.065, 0.065, 0.126, 0x607a7a, x, 0.18, z, { segments: 16, roughness: 0.38, metalness: 0.35 }).rotation.z = Math.PI / 2;
      }
    }
    addCylinder(robot, 0.045, 0.055, 0.32, 0x597d7b, 0, 0.63, -0.23, { segments: 16, metalness: 0.25 });
    const sensor = new THREE.Mesh(new THREE.SphereGeometry(0.095, 16, 12), new THREE.MeshBasicMaterial({ color: 0x57e8dc }));
    sensor.position.set(0, 0.81, -0.23);
    robot.add(sensor);
    addBox(robot, 0.72, 0.07, 0.56, 0xe0c889, 0, 0.54, 0, { roughness: 0.5 });
    addBox(robot, 0.25, 0.17, 0.25, 0xf2dba0, -0.17, 0.66, 0.02, { roughness: 0.65 });
    addBox(robot, 0.23, 0.15, 0.22, 0x9cbd81, 0.16, 0.65, -0.02, { roughness: 0.7 });
    addCylinder(robot, 0.09, 0.10, 0.18, 0xe8e5d2, 0.17, 0.66, 0.22, { segments: 20 });
    addCylinder(robot, 0.095, 0.095, 0.035, 0x4a6f69, 0.17, 0.77, 0.22, { segments: 20 });
    deliveryGroup.add(robot);
    robot.position.copy(routePoints[0]);

    return {
      group: deliveryGroup,
      robot,
      routePoints,
      start: routePoints[0].clone(),
      targetPosition: new THREE.Vector3(tableX, 0.9, tableZ),
    };
  }

  function addLaserLabScene() {
    addBox(labGroup, 3.5, 0.16, 2.5, 0x40535f, 0, 0.3, 0, { metalness: 0.44, roughness: 0.32 });
    addBox(labGroup, 3.4, 0.035, 2.4, 0x839aa2, 0, 0.398, 0, { metalness: 0.48, roughness: 0.28 });
    for (const x of [-1.45, 1.45]) {
      for (const z of [-0.95, 0.95]) {
        addBox(labGroup, 0.12, 0.62, 0.12, 0x293940, x, -0.09, z, { metalness: 0.48 });
      }
    }

    const wafer = addCylinder(labGroup, 0.76, 0.76, 0.055, 0x4d697f, 0, 0.454, 0, { segments: 64, roughness: 0.26, metalness: 0.46 });
    wafer.name = 'mock_silicon_wafer';
    const waferFace = new THREE.Mesh(
      new THREE.CircleGeometry(0.70, 64),
      new THREE.MeshBasicMaterial({ color: 0x71c2d6, transparent: true, opacity: 0.46, side: THREE.DoubleSide }),
    );
    waferFace.rotation.x = -Math.PI / 2;
    waferFace.position.set(0, 0.485, 0);
    labGroup.add(waferFace);
    const waferRim = new THREE.Mesh(
      new THREE.TorusGeometry(0.72, 0.025, 10, 64),
      makeMaterial(0x95cfe0, 0.25, 0.42),
    );
    waferRim.rotation.x = Math.PI / 2;
    waferRim.position.set(0, 0.49, 0);
    labGroup.add(waferRim);

    for (const x of [-1.35, 1.35]) {
      addBox(labGroup, 0.14, 1.25, 0.16, 0x526771, x, 1.16, 0, { metalness: 0.54, roughness: 0.34 });
      addBox(labGroup, 0.20, 0.18, 0.22, 0x7b929a, x, 1.78, 0, { metalness: 0.5 });
    }
    addBox(labGroup, 2.9, 0.18, 0.22, 0x4f626d, 0, 1.78, 0, { metalness: 0.52, roughness: 0.32 });
    addBox(labGroup, 0.62, 0.16, 0.52, 0x24343d, 1.0, 0.74, -0.72, { metalness: 0.34 });
    addBox(labGroup, 0.11, 0.20, 0.04, 0xb82039, 1.0, 0.75, -0.445, { roughness: 0.26 });

    const head = new THREE.Group();
    head.name = 'mock_laser_gantry_head';
    addBox(head, 0.38, 0.23, 0.38, 0x72818a, 0, 0, 0, { metalness: 0.58, roughness: 0.27 });
    addCylinder(head, 0.08, 0.055, 0.18, 0x2b343a, 0, -0.2, 0, { segments: 20, metalness: 0.4 });
    const beam = new THREE.Mesh(
      new THREE.CylinderGeometry(0.035, 0.075, 0.88, 18),
      new THREE.MeshBasicMaterial({ color: 0xff3d62, transparent: true, opacity: 0.38, depthWrite: false }),
    );
    beam.position.set(0, -0.72, 0);
    beam.visible = false;
    head.add(beam);
    labGroup.add(head);
    head.position.set(-0.86, 1.58, 0);

    const spot = new THREE.Mesh(
      new THREE.CircleGeometry(0.12, 28),
      new THREE.MeshBasicMaterial({ color: 0xff4865, transparent: true, opacity: 0.55, side: THREE.DoubleSide }),
    );
    spot.rotation.x = -Math.PI / 2;
    spot.position.set(-0.86, 0.493, 0);
    spot.visible = false;
    labGroup.add(spot);

    const statusLamp = new THREE.Mesh(new THREE.SphereGeometry(0.07, 16, 12), new THREE.MeshBasicMaterial({ color: 0xffbd66 }));
    statusLamp.position.set(1.0, 0.88, -0.72);
    labGroup.add(statusLamp);

    return {
      group: labGroup,
      head,
      beam,
      spot,
      targetPosition: new THREE.Vector3(0, 0.49, 0),
    };
  }

  const delivery = addDeliveryScene();
  const laserLab = addLaserLabScene();

  const scenarios = {
    'blue-vial': {
      label: 'BLUE VIAL · 藥瓶抓取',
      mission: '定位並抓取藍色藥瓶；辨識並避開琥珀色干擾瓶。',
      target: 'BLUE VIAL',
      code: 'class · blue_vial',
      confidence: '0.96',
      detected: '已定位 · 合成 HUD',
      distractor: '琥珀瓶 · 排除',
      bbox: 'BLUE_VIAL · bbox_2d_tight',
      mask: 'MASK / blue_vial',
      bboxLine: 'bbox_2d_tight  [31, 20, 49, 47]',
      note: '藍色藥瓶抓取流程是瀏覽器端 mock；未執行 Isaac Sim、AI 推論或真機控制。',
      view: 'TOP CAM · RGB + SEMANTIC MASK · SYNTHETIC FRAME 07',
      legend: '<div class="legend-chip"><i class="legend-dot"></i>目標 / blue_vial</div><div class="legend-chip"><i class="legend-dot amber"></i>琥珀干擾瓶</div><div class="legend-chip"><i class="legend-dot mask"></i>語意遮罩</div>',
      dataTitle: 'DATA CONTRACT / BLUE VIAL MOCK',
      dataStats: [['100', '程序化影像'], ['64×64', 'RGB + mask'], ['80 / 20', '藍瓶 / 負樣本'], ['81/10/9', 'train / val / test']],
      links: true,
      footer: 'BLUE VIAL · SYNTHETIC PICK & PLACE MOCK',
      warning: 'MOCK ONLY · NO HARDWARE / NO ISAAC RUNTIME',
      iconClass: '',
      stepTitle: '抓取序列',
      stepHints: ['RGB + MASK', 'BLUE ONLY', 'SAFE PATH', 'GRIP MOCK', 'TRAJECTORY', 'DONE'],
      steps: ['視覺掃描', '目標對位', '垂直接近', '夾取確認', '提起並轉運', '放入目標區'],
      phaseCaption: '合成 RGB / mask 合約',
      overlay: null,
    },
    delivery: {
      label: '餐飲配送 · 送餐機器人',
      mission: '將模擬餐點送到指定桌位，沿合成路徑繞過障礙；不連接配送平台或實體機器人。',
      target: 'MEAL TRAY',
      code: 'class · meal_tray_mock',
      confidence: 'MOCK',
      detected: '餐點已定位 · MOCK HUD',
      distractor: '路線障礙 · 模擬避讓',
      bbox: 'MEAL_TRAY · bbox_2d_tight · MOCK',
      mask: 'MASK / meal_tray · MOCK',
      bboxLine: 'bbox_2d_tight  [42, 28, 68, 72] · MOCK',
      note: '送餐車沿預設路線巡航的瀏覽器模擬。沒有真實導航、餐點配送、電梯/門禁整合或硬體連線。',
      view: 'SERVICE ROUTE · SYNTHETIC MEAL TRAY / MOCK OBSTACLE',
      legend: '<div class="legend-chip"><i class="legend-dot"></i>餐點目標 · MOCK</div><div class="legend-chip"><i class="legend-dot amber"></i>障礙物 · MOCK</div><div class="legend-chip"><i class="legend-dot mask"></i>合成路徑</div>',
      dataTitle: 'SCENARIO CONTRACT / DELIVERY MOCK',
      dataStats: [['MOCK', '程序化場景'], ['N/A', '無實際訂單'], ['No AI', '無模型推論'], ['No robot', '無硬體連線']],
      links: false,
      footer: 'FOOD DELIVERY ROBOT · BROWSER MOCK ROUTE',
      warning: 'MOCK ONLY · NO REAL DELIVERY / NO HARDWARE',
      iconClass: 'scenario-delivery',
      stepTitle: '送餐任務序列',
      stepHints: ['ROUTE SCAN', 'MOCK NAV', 'AVOID MOCK', 'DROP MOCK'],
      steps: ['掃描餐點與桌位', '沿合成路線行駛', '繞過模擬障礙', '抵達並完成交付'],
      phaseCaption: '預設路線 · 瀏覽器模擬',
      overlay: delivery.targetPosition,
    },
    'laser-coating': {
      label: '半導體實驗室 · 雷射鍍膜',
      mission: '在虛構晶圓台展示一段雷射鍍膜路徑；光束只作視覺示意，不發射雷射、不沉積材料。',
      target: 'SILICON WAFER',
      code: 'class · wafer_mock',
      confidence: 'MOCK',
      detected: '晶圓定位 · MOCK HUD',
      distractor: '安全互鎖 · 示意元件',
      bbox: 'WAFER · bbox_2d_tight · MOCK',
      mask: 'MASK / wafer_mock · MOCK',
      bboxLine: 'bbox_2d_tight  [25, 18, 76, 81] · MOCK',
      note: '半導體實驗室的視覺化情境，不是製程模擬器。沒有雷射發射、材料沉積、設備控制、製程參數或實驗結果。',
      view: 'CLEANROOM MOCK · WAFER TABLE / VISUAL-ONLY BEAM',
      legend: '<div class="legend-chip"><i class="legend-dot"></i>晶圓樣品 · MOCK</div><div class="legend-chip"><i class="legend-dot amber"></i>互鎖示意</div><div class="legend-chip"><i class="legend-dot mask"></i>虛構掃描路徑</div>',
      dataTitle: 'SCENARIO CONTRACT / PROCESS MOCK',
      dataStats: [['MOCK', '程序化場景'], ['N/A', '無製程數據'], ['No laser', '不發射雷射'], ['No process', '不沉積材料']],
      links: false,
      footer: 'SEMICONDUCTOR LAB · VISUAL-ONLY COATING MOCK',
      warning: 'MOCK ONLY · NO LASER / NO MATERIAL PROCESS / NO HARDWARE',
      iconClass: 'scenario-laser',
      stepTitle: '實驗流程示意',
      stepHints: ['WAFER MOCK', 'GATE MOCK', 'PATH MOCK', 'NO PROCESS'],
      steps: ['晶圓定位（模擬）', '互鎖狀態示意', '掃描路徑示意', '結束（無實際鍍膜）'],
      phaseCaption: '虛構路徑 · 不執行製程',
      overlay: laserLab.targetPosition,
    },
  };

  let currentScenario = 'blue-vial';
  let scenarioRunning = false;
  let scenarioPaused = false;
  let scenarioElapsed = 0;
  let scenarioCompleted = false;
  let scenarioStep = 0;
  let lastTick = performance.now();
  const runCounts = { delivery: 0, 'laser-coating': 0 };

  function currentMode() {
    return $('sceneMode').textContent.trim();
  }

  function setScenarioStatus(status) {
    runtime.setStatus(`${currentMode()} / ${status} · MOCK`);
  }

  function updateModeNote(config) {
    $('modeNote').textContent = currentMode() === 'HIL'
      ? `HIL 人工確認僅為本頁模擬閘門；${config.label} 不會連接硬體或外部系統。`
      : `${config.label} 只在瀏覽器執行合成情境，不連接真實機器人或製程設備。`;
  }

  function updateStepDisplay(index, completed = false) {
    if (currentScenario === 'blue-vial') return;
    const stepNodes = document.querySelectorAll('#steps .step');
    stepNodes.forEach((node, nodeIndex) => {
      node.classList.toggle('active', scenarioRunning && nodeIndex === index);
      node.classList.toggle('done', completed || nodeIndex < index);
    });
    const count = scenarios[currentScenario].steps.length;
    $('stepCounter').textContent = `${scenarioRunning ? index + 1 : completed ? count : 0} / ${count}`;
  }

  function updateScenarioUI(id) {
    const config = scenarios[id];
    document.querySelector('.taskbox').value = config.mission;
    document.querySelector('.target-name').textContent = config.target;
    document.querySelector('.target-code').textContent = config.code;
    document.querySelector('.target-icon').className = `target-icon ${config.iconClass}`.trim();
    document.querySelector('.confidence strong').textContent = config.confidence;
    document.querySelector('.confidence span').textContent = config.confidence === 'MOCK' ? 'STATIC MOCK' : 'DEMO SCORE';
    const scanRows = document.querySelectorAll('.target-card .scan-item');
    scanRows[0].querySelector('strong').textContent = config.detected;
    scanRows[1].querySelector('strong').textContent = config.distractor;
    document.querySelector('.bbox-label').textContent = config.bbox;
    maskLabel.textContent = config.mask;
    maskLabel.style.display = id !== 'blue-vial' && $('maskToggle').classList.contains('on') ? 'block' : 'none';
    document.querySelector('.bbox-line').textContent = config.bboxLine;
    document.querySelector('.v-top .micro').textContent = config.view;
    document.querySelector('.v-bottom').innerHTML = config.legend;
    document.querySelector('.mock-note').textContent = config.note;
    document.querySelector('.data-title').textContent = config.dataTitle;
    document.querySelectorAll('.data-stat').forEach((stat, index) => {
      stat.querySelector('strong').textContent = config.dataStats[index][0];
      stat.querySelector('span').textContent = config.dataStats[index][1];
    });
    document.querySelector('.source-links').style.display = config.links ? 'flex' : 'none';
    document.querySelector('footer > span').textContent = config.footer;
    document.querySelector('.footer-right .warning').textContent = config.warning;
    document.querySelector('.side.right .section:nth-child(2) .sect-title').textContent = config.stepTitle;
    document.querySelector('.metrics .metric:nth-child(1) .metric-name').textContent = id === 'blue-vial' ? 'Episode' : 'Scenario run';
    document.querySelector('.metrics .metric:nth-child(1) .metric-caption').textContent = id === 'blue-vial' ? '合成資料框索引' : '此數值為本頁模擬次數';
    document.querySelector('.metrics .metric:nth-child(3) .metric-name').textContent = id === 'blue-vial' ? 'Pick attempts' : 'Mock deliveries / runs';
    document.querySelector('.metrics .metric:nth-child(3) .metric-caption').textContent = id === 'blue-vial' ? '本工作階段模擬計數' : '不是實際任務或實驗數據';
    $('episode').innerHTML = id === 'blue-vial'
      ? '07 <small>/ 100</small>'
      : `${String(runCounts[id] + 1).padStart(2, '0')} <small>/ MOCK</small>`;
    $('pickCount').textContent = id === 'blue-vial' ? '00' : String(runCounts[id]).padStart(2, '0');
    $('phaseMetric').textContent = '待命';
    $('phaseCaption').textContent = config.phaseCaption;
    $('steps').innerHTML = id === 'blue-vial'
      ? blueStepHtml
      : config.steps.map((step, index) => `<div class="step" data-scenario-step="${index}">${step}<small>${config.stepHints[index]}</small></div>`).join('');
    $('stepCounter').textContent = id === 'blue-vial' ? '0 / 6' : `0 / ${config.steps.length}`;
    $('runBtn').textContent = id === 'blue-vial' ? '▶　執行抓取' : '▶　執行情境任務';
    updateModeNote(config);
  }

  function resetScenarioPose() {
    delivery.robot.position.copy(delivery.start);
    delivery.robot.rotation.y = 0;
    laserLab.head.position.set(-0.86, 1.58, 0);
    laserLab.beam.visible = false;
    laserLab.spot.visible = false;
  }

  function resetScenario() {
    scenarioRunning = false;
    scenarioPaused = false;
    scenarioElapsed = 0;
    scenarioCompleted = false;
    scenarioStep = 0;
    resetScenarioPose();
    viewport.classList.remove('scanning');
    $('runBtn').textContent = '▶　執行情境任務';
    $('phaseMetric').textContent = '待命';
    $('phaseCaption').textContent = scenarios[currentScenario].phaseCaption;
    $('pickCount').textContent = String(runCounts[currentScenario]).padStart(2, '0');
    $('stepCounter').textContent = `0 / ${scenarios[currentScenario].steps.length}`;
    updateStepDisplay(0, false);
    setScenarioStatus('READY');
  }

  function selectScenario(id) {
    if (!scenarios[id]) return;
    if ($('estop').classList.contains('latched')) {
      scenarioSelect.value = currentScenario;
      runtime.showToast('先清除 E-STOP 鎖存，再切換情境。');
      return;
    }
    if (scenarioRunning) {
      scenarioSelect.value = currentScenario;
      runtime.showToast('任務執行中，請先重置再切換情境。');
      return;
    }
    scenarioRunning = false;
    scenarioPaused = false;
    runtime.resetBlue();
    runtime.resetHilConfirmation();
    currentScenario = id;
    runtime.activeScenario = id;
    blueSceneObjects.forEach(object => { object.visible = id === 'blue-vial'; });
    deliveryGroup.visible = id === 'delivery';
    labGroup.visible = id === 'laser-coating';
    resetScenarioPose();
    scenarioSelect.value = id;
    updateScenarioUI(id);
    setScenarioStatus('READY');
  }

  function updateDelivery(progress) {
    const points = delivery.routePoints;
    const segmentCount = points.length - 1;
    const scaled = Math.min(segmentCount - 0.000001, progress * segmentCount);
    const segment = Math.floor(scaled);
    const local = Math.max(0, Math.min(1, scaled - segment));
    const start = points[segment];
    const end = points[segment + 1];
    delivery.robot.position.lerpVectors(start, end, local);
    delivery.robot.rotation.y = Math.atan2(end.x - start.x, end.z - start.z);
  }

  function updateLaser(progress) {
    const x = -0.86 + 1.72 * progress;
    laserLab.head.position.x = x;
    laserLab.spot.position.x = x;
    laserLab.beam.visible = progress > 0.04 && progress < 0.98;
    laserLab.spot.visible = laserLab.beam.visible;
  }

  function startOrPauseScenario() {
    if ($('estop').classList.contains('latched') || runtime.getStopped()) {
      runtime.showToast('急停鎖存中：先清除 E-STOP，再重置情境。');
      return;
    }
    if (currentMode() === 'HIL' && !$('confirmBtn').classList.contains('confirmed')) {
      runtime.showToast('HIL 模式需要先確認模擬工作區。');
      $('confirmBtn').focus();
      return;
    }
    if (scenarioRunning) {
      scenarioPaused = !scenarioPaused;
      $('runBtn').textContent = scenarioPaused ? '▶　繼續' : 'Ⅱ　暫停';
      return;
    }
    resetScenarioPose();
    scenarioRunning = true;
    scenarioPaused = false;
    scenarioElapsed = 0;
    scenarioCompleted = false;
    scenarioStep = 0;
    viewport.classList.add('scanning');
    $('runBtn').textContent = 'Ⅱ　暫停';
    $('phaseMetric').textContent = scenarios[currentScenario].steps[0];
    $('phaseCaption').textContent = scenarios[currentScenario].phaseCaption;
    $('episode').innerHTML = `${String(runCounts[currentScenario] + 1).padStart(2, '0')} <small>/ MOCK</small>`;
    $('pickCount').textContent = String(runCounts[currentScenario]).padStart(2, '0');
    updateStepDisplay(0, false);
    setScenarioStatus('RUNNING');
    runtime.showToast(currentScenario === 'laser-coating'
      ? '啟動視覺示意 · 不發射雷射、不執行鍍膜'
      : '啟動送餐路線 mock · 不連接真實配送服務');
  }

  function animateScenario(now) {
    const dt = Math.min(0.05, Math.max(0, (now - lastTick) / 1000));
    lastTick = now;
    if (currentScenario !== 'blue-vial' && scenarioRunning && !scenarioPaused) {
      if ($('estop').classList.contains('latched')) {
        scenarioRunning = false;
        scenarioPaused = false;
        viewport.classList.remove('scanning');
      } else {
        scenarioElapsed += dt;
        const progress = Math.min(1, scenarioElapsed / SCENARIO_RUN_SECONDS);
        if (currentScenario === 'delivery') updateDelivery(progress);
        if (currentScenario === 'laser-coating') updateLaser(progress);
        const steps = scenarios[currentScenario].steps;
        scenarioStep = Math.min(steps.length - 1, Math.floor(progress * steps.length));
        $('phaseMetric').textContent = steps[scenarioStep];
        updateStepDisplay(scenarioStep, false);
        if (progress >= 1) {
          scenarioRunning = false;
          scenarioPaused = false;
          scenarioCompleted = true;
          runCounts[currentScenario] += 1;
          viewport.classList.remove('scanning');
          $('runBtn').textContent = '▶　再跑一次';
          $('phaseMetric').textContent = '完成';
          $('phaseCaption').textContent = scenarios[currentScenario].phaseCaption;
          $('episode').innerHTML = `${String(runCounts[currentScenario]).padStart(2, '0')} <small>/ MOCK</small>`;
          $('pickCount').textContent = String(runCounts[currentScenario]).padStart(2, '0');
          setScenarioStatus('COMPLETE');
          updateStepDisplay(steps.length - 1, true);
          runtime.showToast(currentScenario === 'laser-coating'
            ? '視覺示意完成 · 無雷射發射或材料沉積'
            : '模擬送餐路線完成 · 非實際配送');
        }
      }
    }
    requestAnimationFrame(animateScenario);
  }

  function updateMockOverlay() {
    if (currentScenario !== 'blue-vial') {
      const target = scenarios[currentScenario].overlay;
      const rect = runtime.renderer.domElement.getBoundingClientRect();
      const point = target.clone().project(runtime.camera);
      const x = (point.x * 0.5 + 0.5) * rect.width;
      const y = (-point.y * 0.5 + 0.5) * rect.height;
      bbox.style.left = `${Math.max(8, Math.min(rect.width - 112, x - 56))}px`;
      bbox.style.top = `${Math.max(28, Math.min(rect.height - 100, y - 44))}px`;
      bbox.style.width = '112px';
      bbox.style.height = '88px';
      maskLabel.style.left = `${Math.max(8, Math.min(rect.width - 120, x - 54))}px`;
      maskLabel.style.top = `${Math.max(32, Math.min(rect.height - 26, y + 50))}px`;
    }
    requestAnimationFrame(updateMockOverlay);
  }

  scenarioSelect.addEventListener('change', () => selectScenario(scenarioSelect.value));
  $('runBtn').addEventListener('click', event => {
    if (currentScenario === 'blue-vial') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    startOrPauseScenario();
  }, true);
  $('resetBtn').addEventListener('click', event => {
    if (currentScenario === 'blue-vial') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if ($('estop').classList.contains('latched')) {
      runtime.showToast('先清除 E-STOP 鎖存，再重置情境。');
      return;
    }
    resetScenario();
    runtime.showToast('情境已重置 · mock only');
  }, true);
  $('estop').addEventListener('click', () => {
    if (currentScenario === 'blue-vial') return;
    scenarioRunning = false;
    scenarioPaused = false;
    $('runBtn').textContent = '▶　執行情境任務';
    viewport.classList.remove('scanning');
  });
  $('resetEstop').addEventListener('click', () => {
    if (currentScenario === 'blue-vial') return;
    runtime.resetHilConfirmation();
    resetScenario();
    runtime.showToast('急停鎖存已清除 · 情境仍為瀏覽器模擬');
  });
  document.querySelectorAll('.mode').forEach(button => {
    button.addEventListener('click', event => {
      if (currentScenario !== 'blue-vial' && scenarioRunning) {
        event.preventDefault();
        event.stopImmediatePropagation();
        runtime.showToast('任務執行中不能切換 SIL/HIL 模式。');
      }
    }, true);
    button.addEventListener('click', () => {
      if (currentScenario !== 'blue-vial') {
        runtime.resetHilConfirmation();
        updateModeNote(scenarios[currentScenario]);
        if (!$('estop').classList.contains('latched')) setScenarioStatus('READY');
      }
    });
  });

  const initialScenario = scenarioSelect.value || 'blue-vial';
  currentScenario = initialScenario;
  runtime.activeScenario = initialScenario;
  updateScenarioUI(initialScenario);
  requestAnimationFrame(animateScenario);
  requestAnimationFrame(updateMockOverlay);
})();

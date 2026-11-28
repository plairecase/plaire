import React, {useEffect, useMemo, useState} from 'react';
import {ThreeCanvas} from '@remotion/three';
import {continueRender, delayRender, Easing, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import * as THREE from 'three';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {palette} from '../brand';

export type Scene3D = 'hero' | 'fly';

/** Модель .glb: нормируем по наибольшей стороне, центрируем, Y вверх (раздел 8 инструкции). */
const useModel = (src: string) => {
  const [obj, setObj] = useState<THREE.Object3D | null>(null);
  const [handle] = useState(() => delayRender(`3D ${src}`));
  useEffect(() => {
    new GLTFLoader().load(
      staticFile(src),
      (g) => {
        const root = g.scene;
        const box = new THREE.Box3().setFromObject(root);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const s = 1 / Math.max(size.x, size.y, size.z);
        root.position.sub(center.multiplyScalar(1));
        const wrap = new THREE.Group();
        wrap.add(root);
        wrap.scale.setScalar(s);
        root.traverse((o) => {
          if ((o as THREE.Mesh).isMesh) {
            (o as THREE.Mesh).castShadow = true;
          }
        });
        setObj(wrap);
        continueRender(handle);
      },
      undefined,
      (e) => {
        throw new Error('Не загрузилась 3D-модель ' + src + ': ' + e);
      },
    );
  }, [src, handle]);
  return obj;
};

const Model: React.FC<{obj: THREE.Object3D; scene: Scene3D; total: number; frame: number}> = ({obj, scene, total, frame}) => {
  const clone = useMemo(() => obj.clone(true), [obj]);
  if (!clone) return null;
  const ease = Easing.bezier(0.16, 1, 0.3, 1);
  let rotY = 0, rotX = 0.35, scale = 1, y = 0, z = 0;
  if (scene === 'hero') {
    // финал: медленный поворот 0 → 200°, лёгкое парение; чехол ниже текста
    const p = interpolate(frame, [0, total], [0, 1], {easing: ease, extrapolateRight: 'clamp'});
    rotY = -0.6 + p * (200 * Math.PI) / 180;
    y = -0.26 + 0.015 * Math.sin(frame / 12);       // центр чехла ≈ 62 % высоты кадра, под ценой
    scale = 0.64;
  } else {
    // переход: чехол влетает, вращаясь, закрывает кадр в середине (там склейка) и пролетает сквозь камеру
    const p = frame / Math.max(1, total);
    rotY = p * Math.PI * 2.2;
    rotX = 0.5 - p * 0.6;
    // полностью закрывает кадр лишь 2–3 кадра (иначе читается как «пустая вставка»)
    scale = interpolate(p, [0, 0.62, 0.8, 1], [0.25, 2.4, 6, 14], {easing: Easing.in(Easing.quad)});
    z = 0;
  }
  return (
    <group position={[0, y, z]} rotation={[rotX, rotY, 0]} scale={scale}>
      <primitive object={clone} />
    </group>
  );
};

export const Case3D: React.FC<{src: string; scene: Scene3D; total: number}> = ({src, scene, total}) => {
  const {width, height} = useVideoConfig();
  const frame = useCurrentFrame();
  const obj = useModel(src);
  return (
    <div style={{position: 'absolute', inset: 0, background: scene === 'hero' ? palette.paper : 'transparent'}}>
      <ThreeCanvas width={width} height={height} shadows camera={{fov: 30, position: [0, 0, 4]}}
        gl={{alpha: true, antialias: true, preserveDrawingBuffer: true}}>
        <ambientLight intensity={0.55} />
        <directionalLight position={[-2.5, 3, 3]} intensity={2.2} castShadow
          shadow-mapSize-width={1024} shadow-mapSize-height={1024} />
        <directionalLight position={[3, 1, 2]} intensity={0.6} />
        {scene === 'hero' ? (
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.5, 0]} receiveShadow>
            <planeGeometry args={[10, 10]} />
            <shadowMaterial opacity={0.18} />
          </mesh>
        ) : null}
        {obj ? <Model obj={obj} scene={scene} total={total} frame={frame} /> : null}
      </ThreeCanvas>
    </div>
  );
};

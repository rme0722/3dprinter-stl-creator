'use client'

import { useRef, useEffect, Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, useGLTF, PerspectiveCamera, Grid, Environment } from '@react-three/drei'
import { Mesh } from 'three'
import * as THREE from 'three'

interface ModelProps {
  url: string
}

function Model({ url }: ModelProps) {
  const { scene } = useGLTF(url)
  
  useEffect(() => {
    // Center and scale the model
    const box = new THREE.Box3().setFromObject(scene)
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3())
    
    const maxDim = Math.max(size.x, size.y, size.z)
    const scale = 10 / maxDim
    
    scene.position.sub(center)
    scene.scale.multiplyScalar(scale)
    
    // Apply material to all meshes
    scene.traverse((child) => {
      if ((child as Mesh).isMesh) {
        const mesh = child as Mesh
        mesh.material = new THREE.MeshPhongMaterial({
          color: 0x888888,
          specular: 0x111111,
          shininess: 200,
        })
      }
    })
  }, [scene])
  
  return <primitive object={scene} />
}

interface STLViewerProps {
  modelUrl: string
  className?: string
}

export function STLViewer({ modelUrl, className = '' }: STLViewerProps) {
  return (
    <div className={`w-full h-full bg-gray-100 rounded-lg ${className}`}>
      <Canvas>
        <PerspectiveCamera makeDefault position={[15, 15, 15]} />
        <OrbitControls 
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
        />
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <Suspense fallback={null}>
          <Model url={modelUrl} />
        </Suspense>
        <Grid 
          args={[20, 20]} 
          cellSize={1} 
          cellThickness={0.5} 
          cellColor={'#6b7280'} 
          sectionSize={5} 
          sectionThickness={1}
          sectionColor={'#374151'}
          fadeDistance={30}
          fadeStrength={1}
          followCamera={false}
        />
        <Environment preset="studio" />
      </Canvas>
    </div>
  )
}

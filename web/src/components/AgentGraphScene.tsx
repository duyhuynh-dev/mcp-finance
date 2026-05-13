import { useEffect, useRef } from 'react'
import * as THREE from 'three'

export default function AgentGraphScene() {
  const mountRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return undefined

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(42, mount.clientWidth / mount.clientHeight, 0.1, 100)
    camera.position.set(0, 1.8, 9)

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      return setupCanvasFallback(mount)
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    mount.appendChild(renderer.domElement)

    const group = new THREE.Group()
    group.position.set(2.4, 0, 0)
    scene.add(group)

    const agentMat = new THREE.MeshStandardMaterial({ color: '#818cf8', roughness: 0.32, metalness: 0.25 })
    const riskMat = new THREE.MeshStandardMaterial({ color: '#34d399', roughness: 0.28, metalness: 0.2 })
    const auditMat = new THREE.MeshStandardMaterial({ color: '#fbbf24', roughness: 0.42, metalness: 0.08 })
    const mutedMat = new THREE.MeshStandardMaterial({ color: '#71717a', roughness: 0.55, metalness: 0.1 })
    const lineMat = new THREE.LineBasicMaterial({ color: '#3f465a', transparent: true, opacity: 0.75 })
    const pulseMat = new THREE.MeshBasicMaterial({ color: '#34d399', transparent: true, opacity: 0.9 })

    const sphere = new THREE.SphereGeometry(0.18, 32, 16)
    const smallSphere = new THREE.SphereGeometry(0.09, 20, 10)
    const nodes = [
      new THREE.Vector3(-3.2, 1.35, 0),
      new THREE.Vector3(-3.2, -1.15, 0.2),
      new THREE.Vector3(-1.05, 0.15, 0),
      new THREE.Vector3(1.15, 0.15, 0),
      new THREE.Vector3(3.05, 1.05, 0.15),
      new THREE.Vector3(3.05, -1.05, -0.1),
    ]

    nodes.forEach((pos, index) => {
      const mesh = new THREE.Mesh(sphere, index < 2 ? agentMat : index < 4 ? riskMat : index === 4 ? mutedMat : auditMat)
      mesh.position.copy(pos)
      group.add(mesh)
    })

    const segments = [
      [nodes[0], nodes[2]],
      [nodes[1], nodes[2]],
      [nodes[2], nodes[3]],
      [nodes[3], nodes[4]],
      [nodes[3], nodes[5]],
    ]

    segments.forEach(([a, b]) => {
      const geometry = new THREE.BufferGeometry().setFromPoints([a, b])
      group.add(new THREE.Line(geometry, lineMat))
    })

    const gate = new THREE.Mesh(
      new THREE.BoxGeometry(0.12, 2.7, 1.6),
      new THREE.MeshStandardMaterial({ color: '#172018', roughness: 0.18, metalness: 0.1, transparent: true, opacity: 0.72 }),
    )
    gate.position.set(0.05, 0.15, 0)
    group.add(gate)

    const torus = new THREE.Mesh(new THREE.TorusGeometry(1.05, 0.012, 12, 96), new THREE.MeshBasicMaterial({ color: '#818cf8', transparent: true, opacity: 0.32 }))
    torus.position.copy(nodes[2])
    group.add(torus)

    const packets = segments.map(([a, b], index) => {
      const packet = new THREE.Mesh(smallSphere, pulseMat.clone())
      packet.position.copy(a)
      group.add(packet)
      return { packet, a, b, offset: index / segments.length }
    })

    const ambient = new THREE.AmbientLight('#ffffff', 0.78)
    const key = new THREE.PointLight('#818cf8', 2.6, 14)
    key.position.set(-3, 4, 5)
    const fill = new THREE.PointLight('#34d399', 2.1, 12)
    fill.position.set(3, -1, 4)
    scene.add(ambient, key, fill)

    let frame = 0
    let animationId = 0
    const clock = new THREE.Clock()

    const resize = () => {
      const width = mount.clientWidth
      const height = mount.clientHeight
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    }

    const animate = () => {
      animationId = window.requestAnimationFrame(animate)
      const t = clock.getElapsedTime()
      group.rotation.y = Math.sin(t * 0.22) * 0.12
      group.rotation.x = Math.sin(t * 0.16) * 0.04
      torus.rotation.z = t * 0.32
      torus.rotation.y = t * 0.18
      gate.scale.y = 1 + Math.sin(t * 1.5) * 0.03
      packets.forEach(({ packet, a, b, offset }) => {
        const k = (t * 0.22 + offset) % 1
        packet.position.lerpVectors(a, b, smooth(k))
        packet.scale.setScalar(0.8 + Math.sin((k + frame * 0.01) * Math.PI) * 0.45)
      })
      renderer.render(scene, camera)
      frame += 1
    }

    window.addEventListener('resize', resize)
    resize()
    animate()

    return () => {
      window.removeEventListener('resize', resize)
      window.cancelAnimationFrame(animationId)
      mount.removeChild(renderer.domElement)
      scene.traverse((obj) => {
        if (obj instanceof THREE.Mesh || obj instanceof THREE.Line) {
          obj.geometry.dispose()
          if (Array.isArray(obj.material)) {
            obj.material.forEach((material) => material.dispose())
          } else {
            obj.material.dispose()
          }
        }
      })
      renderer.dispose()
    }
  }, [])

  return <div ref={mountRef} className="absolute inset-0" aria-hidden="true" />
}

function smooth(x: number) {
  return x * x * (3 - 2 * x)
}

function setupCanvasFallback(mount: HTMLDivElement) {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) return undefined

  mount.appendChild(canvas)
  let animationId = 0
  let time = 0

  const resize = () => {
    const ratio = Math.min(window.devicePixelRatio || 1, 2)
    canvas.width = Math.max(1, Math.floor(mount.clientWidth * ratio))
    canvas.height = Math.max(1, Math.floor(mount.clientHeight * ratio))
    canvas.style.width = `${mount.clientWidth}px`
    canvas.style.height = `${mount.clientHeight}px`
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  }

  const draw = () => {
    animationId = window.requestAnimationFrame(draw)
    const width = mount.clientWidth
    const height = mount.clientHeight
    time += 0.012
    ctx.clearRect(0, 0, width, height)

    const cx = width * 0.67
    const cy = height * 0.52
    const scale = Math.min(width, height) / 640
    const nodes = [
      [cx - 230 * scale, cy - 100 * scale, '#818cf8'],
      [cx - 230 * scale, cy + 105 * scale, '#818cf8'],
      [cx - 60 * scale, cy, '#34d399'],
      [cx + 105 * scale, cy, '#34d399'],
      [cx + 255 * scale, cy - 82 * scale, '#71717a'],
      [cx + 255 * scale, cy + 86 * scale, '#fbbf24'],
    ] as const
    const links = [[0, 2], [1, 2], [2, 3], [3, 4], [3, 5]]

    ctx.lineWidth = 1
    links.forEach(([from, to], index) => {
      const a = nodes[from]
      const b = nodes[to]
      ctx.strokeStyle = 'rgba(99, 110, 140, 0.45)'
      ctx.beginPath()
      ctx.moveTo(a[0], a[1])
      ctx.lineTo(b[0], b[1])
      ctx.stroke()

      const k = smooth((time * 0.22 + index / links.length) % 1)
      const px = a[0] + (b[0] - a[0]) * k
      const py = a[1] + (b[1] - a[1]) * k
      ctx.fillStyle = 'rgba(52, 211, 153, 0.9)'
      ctx.beginPath()
      ctx.arc(px, py, 4 + Math.sin(k * Math.PI) * 3, 0, Math.PI * 2)
      ctx.fill()
    })

    ctx.strokeStyle = 'rgba(52, 211, 153, 0.22)'
    ctx.lineWidth = 2
    ctx.strokeRect(cx - 10 * scale, cy - 145 * scale, 16 * scale, 290 * scale)

    nodes.forEach(([x, y, color], index) => {
      ctx.fillStyle = color
      ctx.globalAlpha = 0.9
      ctx.beginPath()
      ctx.arc(x, y + Math.sin(time * 2 + index) * 3, 11 * scale, 0, Math.PI * 2)
      ctx.fill()
    })
    ctx.globalAlpha = 1
  }

  window.addEventListener('resize', resize)
  resize()
  draw()

  return () => {
    window.removeEventListener('resize', resize)
    window.cancelAnimationFrame(animationId)
    mount.removeChild(canvas)
  }
}

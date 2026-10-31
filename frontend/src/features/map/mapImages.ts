/** Canvas-drawn map icons: independent of basemap glyphs and crisp on high-DPI screens. */

const SHIELD_PATH =
  'M3 4c5 1.6 11 1.6 17-1.8C26 5.6 32 5.6 37 4c2 9.5 2.4 18.6-.5 25.6C33.4 37 27 40.4 20 42c-7-1.6-13.4-5-16.5-12.4C.6 22.6 1 13.5 3 4Z'

export interface IconImage {
  width: number
  height: number
  data: Uint8ClampedArray
  pixelRatio: number
}

function draw(
  width: number,
  height: number,
  paint: (ctx: CanvasRenderingContext2D) => void,
): IconImage {
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  const canvas = document.createElement('canvas')
  canvas.width = width * ratio
  canvas.height = height * ratio
  const ctx = canvas.getContext('2d')!
  ctx.scale(ratio, ratio)
  paint(ctx)
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height)
  return { width: canvas.width, height: canvas.height, data: image.data, pixelRatio: ratio }
}

export function shieldIcon(
  letter: string,
  colors: { fill: string; stroke: string; text: string },
): IconImage {
  return draw(30, 33, (ctx) => {
    ctx.scale(0.72, 0.72)
    ctx.translate(1, 1)
    const path = new Path2D(SHIELD_PATH)
    ctx.fillStyle = colors.fill
    ctx.fill(path)
    ctx.lineWidth = 2.5
    ctx.strokeStyle = colors.stroke
    ctx.stroke(path)
    ctx.fillStyle = colors.text
    ctx.font = '700 20px "Barlow Condensed", "Arial Narrow", sans-serif'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(letter, 20, 24)
  })
}

/** Top-down marker for the truck's projected position: a disc with a heading chevron. */
export function truckIcon(colors: { fill: string; ink: string; halo: string }): IconImage {
  return draw(34, 34, (ctx) => {
    ctx.beginPath()
    ctx.arc(17, 17, 15, 0, Math.PI * 2)
    ctx.fillStyle = colors.halo
    ctx.fill()
    ctx.beginPath()
    ctx.arc(17, 17, 11, 0, Math.PI * 2)
    ctx.fillStyle = colors.fill
    ctx.fill()
    ctx.beginPath()
    ctx.moveTo(17, 9)
    ctx.lineTo(23, 22)
    ctx.lineTo(17, 19)
    ctx.lineTo(11, 22)
    ctx.closePath()
    ctx.fillStyle = colors.ink
    ctx.fill()
  })
}

export function endpointIcon(
  kind: 'origin' | 'destination',
  colors: { fill: string; ink: string },
): IconImage {
  return draw(22, 22, (ctx) => {
    ctx.fillStyle = colors.ink
    ctx.strokeStyle = colors.fill
    ctx.lineWidth = 3
    if (kind === 'origin') {
      ctx.beginPath()
      ctx.arc(11, 11, 7, 0, Math.PI * 2)
      ctx.fill()
      ctx.stroke()
    } else {
      ctx.fillRect(4, 4, 14, 14)
      ctx.strokeRect(4, 4, 14, 14)
    }
  })
}

// The WT logo in the header: a pixel-art watch tower with a light that turns around.
// The animation has 8 frames of 0.5 s (4 s in all). index.css shows one frame at a time.
// With "reduce motion", or with no animation, the still picture shows (light to the left and right).
// public/icon.svg and public/icon-maskable.svg have the same still picture. Change them together.
import { cn } from "@/lib/utils";

/** One pixel rectangle: x, y, width, height on a 32 x 32 grid. */
type Rect = [number, number, number, number];

const BG = "#171717";
const WHITE = "#fafafa";
const AMBER = "#f59e0b";

const TOWER: Rect[] = [
  // Roof
  [15, 5, 2, 1],
  [14, 6, 4, 1],
  [13, 7, 6, 1],
  [12, 8, 8, 1],
  // Lamp room, gallery, body and base
  [12, 9, 8, 4],
  [10, 13, 12, 2],
  [12, 15, 8, 3],
  [11, 18, 10, 4],
  [10, 22, 12, 4],
  [8, 26, 16, 2],
];
const DARK_PARTS: Rect[] = [
  [15, 18, 2, 2], // window
  [15, 23, 2, 3], // door
];
const LAMP: Rect = [13, 10, 6, 2];

// The light beam has 3 parts. A short beam has the 2 parts near the lamp.
// Each part is fainter than the part before it, so the beam looks like light.
const BEAM_OPACITY = [0.9, 0.6, 0.35];
const RIGHT_SHORT: Rect[] = [
  [20, 10, 3, 2],
  [23, 9, 3, 4],
];
const RIGHT_LONG: Rect[] = [...RIGHT_SHORT, [26, 8, 4, 6]];
const LEFT_SHORT: Rect[] = [
  [9, 10, 3, 2],
  [6, 9, 3, 4],
];
const LEFT_LONG: Rect[] = [...LEFT_SHORT, [2, 8, 4, 6]];

/** One animation frame: the beam, and a lamp color when the light points to or away from the viewer. */
interface Frame {
  beam: Rect[];
  lamp?: string;
}

const FRAMES: Frame[] = [
  { beam: RIGHT_LONG },
  { beam: RIGHT_SHORT },
  { beam: [], lamp: "#fef3c7" }, // to the viewer: bright lamp
  { beam: LEFT_SHORT },
  { beam: LEFT_LONG },
  { beam: LEFT_SHORT },
  { beam: [], lamp: "#92400e" }, // away from the viewer: dim lamp
  { beam: RIGHT_SHORT },
];
const FRAME_SECONDS = 0.5;

// A beam: its parts in order from the lamp, each with its opacity.
function Beam({ rects }: { rects: Rect[] }) {
  return (
    <>
      {rects.map((rect, index) => (
        <Pixels key={index} rects={[rect]} fill={AMBER} opacity={BEAM_OPACITY[index]} />
      ))}
    </>
  );
}

function Pixels({ rects, fill, opacity }: { rects: Rect[]; fill: string; opacity?: number }) {
  return (
    <>
      {rects.map(([x, y, width, height]) => (
        <rect key={`${String(x)},${String(y)}`} x={x} y={y} width={width} height={height} fill={fill} opacity={opacity} />
      ))}
    </>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" shapeRendering="crispEdges" aria-hidden="true" className={cn("wt-logo", className)}>
      <rect width="32" height="32" rx="6" fill={BG} />
      <Pixels rects={TOWER} fill={WHITE} />
      <Pixels rects={DARK_PARTS} fill={BG} />
      <Pixels rects={[LAMP]} fill={AMBER} />
      <g className="wt-logo-still">
        <Beam rects={LEFT_LONG} />
        <Beam rects={RIGHT_LONG} />
      </g>
      {FRAMES.map((frame, index) => (
        // The frames never change order, so the position is a good key.
        <g key={index} className="wt-logo-frame" style={{ animationDelay: `${String(index * FRAME_SECONDS)}s` }}>
          <Beam rects={frame.beam} />
          {frame.lamp && <Pixels rects={[LAMP]} fill={frame.lamp} />}
        </g>
      ))}
    </svg>
  );
}

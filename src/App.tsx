import { useState } from 'react';
import { Check, Copy, Download, Terminal } from 'lucide-react';

interface ModeSpec {
  id: 'cube' | 'drawing' | 'puzzle';
  index: string;
  title: string;
  origin: string;
  summary: string;
  gestures: string[];
  fallback: string[];
}

const MODES: ModeSpec[] = [
  {
    id: 'cube',
    index: '01',
    title: 'Liquid Cube',
    origin: 'Subham503/3D-Liquid-Cube-Simulation',
    summary:
      'Interactive 3D shaded cube containing 260 Position-Based Dynamics fluid particles rendered as a soft ROI-accelerated Gaussian liquid body with specular highlights.',
    gestures: [
      'Open hand movement: rotate and tilt the cube with velocity-scaled spin and inertia',
      'Closed fist: freeze rotation and let liquid settle',
      'Thumb + index pinch distance: resize the cube dynamically',
    ],
    fallback: [
      'Mouse drag to rotate cube, mouse wheel or + / - to resize',
      'Space to freeze/unfreeze, R to reset orientation and fluid',
      'M or Esc (or Menu button) to return to the Main Menu',
    ],
  },
  {
    id: 'drawing',
    index: '02',
    title: 'Air Drawing',
    origin: 'RutujaKhule/Gesture-Canvas',
    summary:
      'Persistent neon canvas rendered over the live camera feed with exponential stroke smoothing, bloom glow, anti-gravity sparks, and ambient particles.',
    gestures: [
      'Index finger extended up: draw glowing neon strokes',
      'Closed fist or relaxed hand: pause drawing without leaving trails',
      'Pinch on HUD buttons/swatches: pick colors, toggle Eraser, adjust Brush/Glow, Undo, Clear, Save PNG',
    ],
    fallback: [
      'Mouse drag draws or erases directly on the canvas',
      '1-8 selects neon palette colors, E toggles Eraser, + / - brush, [ / ] glow',
      'U undo, C clear, S save PNG to screenshots/, H help overlay, M or Esc Menu',
    ],
  },
  {
    id: 'puzzle',
    index: '03',
    title: 'Selfie Puzzle',
    origin: 'krishaagor-source/selfie-puzzle-game',
    summary:
      'Capture a live webcam region into a 3x3 shuffled puzzle inside the same window, featuring a live webcam PIP, timer, move counter, preview, and confetti victory.',
    gestures: [
      'Capture phase: pinch-and-drag to draw a box, release to lock, pinch inside to capture',
      'Play phase: pinch-and-hold a tile to lift it, move over target tile, release to swap',
      'Pinch Preview, Restart, New Selfie, or Menu buttons in the side panel',
    ],
    fallback: [
      'Mouse drag to select region (or press F / Quick Selfie for instant center crop)',
      'Mouse drag-and-drop to swap puzzle tiles',
      'P preview, R restart, N new selfie, M or Esc Menu',
    ],
  },
];

const POWERSHELL_COMMANDS = `Expand-Archive -Path .\\combined_camera_studio.zip -DestinationPath .\\
cd .\\combined_camera_studio
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python main.py`;

const LINE_COUNTS = [
  { project: 'Originals combined total (before integration)', physical: '3,248', code: '2,450' },
  { project: 'combined_camera_studio v1 (initial integration)', physical: '1,411', code: '1,203' },
  { project: 'combined_camera_studio v2 (calibration, gestures, FX)', physical: '1,944', code: '1,683' },
  { project: 'combined_camera_studio v3 (AR HUD, One-Euro, ROI liquid, <1.5k)', physical: '1,704', code: '1,465', strong: true },
];

const BENCHMARKS = [
  { screen: 'MENU (AR HUD + FX ON)', before: '43.66 FPS / 14.39 ms', after: '41.51 FPS / 16.63 ms', note: 'vs 40.12 FPS OFF (zero HUD lag)' },
  { screen: 'CALIBRATE', before: '35.73 FPS / 14.10 ms', after: '34.85 FPS / 16.19 ms', note: 'Live ROI box + pinch meter' },
  { screen: 'LIQUID_CUBE', before: '20.81 FPS / 15.90 ms', after: '29.22 FPS / 16.47 ms', note: '+40.4% FPS (half-res ROI glow)' },
  { screen: 'AIR_DRAWING', before: '46.17 FPS / 15.32 ms', after: '43.89 FPS / 16.98 ms', note: 'Tracked stroke + glow LUT' },
  { screen: 'SELFIE_PUZZLE', before: '37.84 FPS / 14.16 ms', after: '46.66 FPS / 17.04 ms', note: '+23.3% FPS (lighter tile loop)' },
];

export default function App() {
  const [selectedMode, setSelectedMode] = useState<ModeSpec['id']>('cube');
  const [copied, setCopied] = useState(false);

  const activeMode = MODES.find((m) => m.id === selectedMode) ?? MODES[0];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(POWERSHELL_COMMANDS);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-8 px-6 py-4">
          <a href="#top" className="text-lg font-bold tracking-tight text-slate-900 whitespace-nowrap shrink-0">
            Combined Camera Studio
          </a>
          <nav aria-label="Primary" className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-600">
            <a href="#modes" className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0">
              Modes
            </a>
            <a href="#setup" className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0">
              Windows Setup
            </a>
            <a href="#camera" className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0">
              Camera URL
            </a>
            <a href="#verification" className="hover:text-slate-900 transition-colors whitespace-nowrap shrink-0">
              Verification
            </a>
          </nav>
          <a
            href="/combined_camera_studio.zip"
            download="combined_camera_studio.zip"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700 transition-colors whitespace-nowrap shrink-0"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            <span>Download ZIP</span>
          </a>
        </div>
      </header>

      <main id="top" className="mx-auto max-w-6xl px-6 py-14 space-y-16">
        <section className="grid grid-cols-1 gap-10 lg:grid-cols-12 items-start">
          <div className="lg:col-span-7 space-y-6">
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
              <span>Windows Desktop Python Application</span>
              <span aria-hidden="true">·</span>
              <span>Single OpenCV Window</span>
              <span aria-hidden="true">·</span>
              <span>MIT Licensed</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl text-balance">
              Three hand-gesture camera apps unified into one studio.
            </h1>
            <p className="max-w-2xl text-base leading-relaxed text-slate-600">
              Combined Camera Studio merges 3D Liquid Cube, Air Drawing, and Selfie Puzzle into a single shared camera
              stream and MediaPipe hand tracker. Select modes from an on-screen menu using index-finger pointing and
              pinch gestures, or switch anytime with keyboard and mouse fallbacks.
            </p>
            <div className="flex flex-wrap items-center gap-4 pt-2">
              <a
                href="/combined_camera_studio.zip"
                download="combined_camera_studio.zip"
                className="inline-flex items-center gap-2.5 rounded-lg bg-blue-700 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700 transition-colors whitespace-nowrap shrink-0"
              >
                <Download className="h-4 w-4" aria-hidden="true" />
                <span>Download combined_camera_studio.zip (5.7 MB)</span>
              </a>
              <a
                href="#setup"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-800 hover:bg-slate-100 transition-colors whitespace-nowrap shrink-0"
              >
                <Terminal className="h-4 w-4 text-slate-600" aria-hidden="true" />
                <span>PowerShell Commands</span>
              </a>
            </div>
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
              Verification notice: Automated headless tests passed using synthetic video, but live physical webcam
              capture and DroidCam URL streaming have not yet been verified on Windows.
            </p>
          </div>

          <div className="lg:col-span-5 rounded-xl border border-slate-200 bg-white p-6 space-y-5">
            <h2 className="text-base font-semibold text-slate-900">Package Contents</h2>
            <dl className="divide-y divide-slate-200 text-sm">
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Entry Point</dt>
                <dd className="font-mono text-slate-900">main.py</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Shared Vision &amp; UI</dt>
                <dd className="font-mono text-slate-900">vision.py, ui_helpers.py</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Mode Modules</dt>
                <dd className="font-mono text-slate-900">modes/*.py</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Hand Model &amp; Tracking</dt>
                <dd className="font-mono text-slate-900">640×480 VIDEO mode</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Calibration, AR HUD &amp; FX</dt>
                <dd className="font-mono text-slate-900">calibration.json / [K] [A] [V]</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Production Code</dt>
                <dd className="font-mono tabular-nums text-slate-900">1,704 physical / 1,465 code</dd>
              </div>
              <div className="flex justify-between py-2.5">
                <dt className="text-slate-500">Originals &amp; Backups</dt>
                <dd className="font-mono text-slate-900">backup_originals/</dd>
              </div>
            </dl>
          </div>
        </section>

        <section id="modes" className="border-t border-slate-200 pt-12 space-y-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">Interactive Modes &amp; Controls</h2>
              <p className="mt-1 text-sm text-slate-600">
                Select a mode below to inspect its gesture controls and keyboard/mouse fallbacks.
              </p>
            </div>
            <div role="tablist" aria-label="Application modes" className="inline-flex rounded-lg bg-slate-200/70 p-1">
              {MODES.map((m) => {
                const active = m.id === selectedMode;
                return (
                  <button
                    key={m.id}
                    type="button"
                    role="tab"
                    aria-selected={active}
                    onClick={() => setSelectedMode(m.id)}
                    className={`rounded-md px-3.5 py-2 text-xs font-semibold transition-colors whitespace-nowrap shrink-0 ${
                      active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {m.index}. {m.title}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-8 space-y-6">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 pb-4">
              <h3 className="text-xl font-bold text-slate-900">
                {activeMode.index}. {activeMode.title}
              </h3>
              <span className="text-xs font-mono text-slate-500">Adapted from {activeMode.origin}</span>
            </div>
            <p className="text-sm leading-relaxed text-slate-600">{activeMode.summary}</p>
            <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-slate-900">Hand Gesture Controls</h4>
                <ul className="space-y-2 text-sm text-slate-600 list-disc pl-5">
                  {activeMode.gestures.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-slate-900">Mouse &amp; Keyboard Fallback</h4>
                <ul className="space-y-2 text-sm text-slate-600 list-disc pl-5">
                  {activeMode.fallback.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        <section id="setup" className="grid grid-cols-1 gap-10 border-t border-slate-200 pt-12 lg:grid-cols-12">
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">Windows PowerShell Setup &amp; Run</h2>
              <button
                type="button"
                onClick={handleCopy}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors whitespace-nowrap shrink-0"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}
                <span>{copied ? 'Copied' : 'Copy Commands'}</span>
              </button>
            </div>
            <p className="text-sm text-slate-600">
              After downloading <code className="text-slate-900">combined_camera_studio.zip</code>, run these commands in
              Windows PowerShell (Python 3.11 or 3.10 recommended):
            </p>
            <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-900 p-5 text-xs leading-6 text-slate-100">
              <code>{POWERSHELL_COMMANDS}</code>
            </pre>
          </div>

          <div id="camera" className="lg:col-span-5 space-y-4">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">Camera &amp; Stream URL</h2>
            <div className="rounded-xl border border-slate-200 bg-white p-6 space-y-4 text-sm text-slate-600">
              <p>
                Open <strong className="font-semibold text-slate-900">Settings (S)</strong> from the Main Menu or pass{' '}
                <code className="text-slate-900">--camera</code> on startup.
              </p>
              <ul className="space-y-2 list-disc pl-5">
                <li>
                  <strong className="font-semibold text-slate-900">Local webcam:</strong> enter an integer index such as{' '}
                  <code className="text-slate-900">0</code> or <code className="text-slate-900">1</code>.
                </li>
                <li>
                  <strong className="font-semibold text-slate-900">Phone / DroidCam / IP camera:</strong> enter the full
                  HTTP/MJPEG or RTSP URL shown by your phone app (e.g.,{' '}
                  <code className="text-slate-900">http://&lt;phone-ip&gt;:&lt;port&gt;/video</code>) and click{' '}
                  <strong className="font-semibold text-slate-900">Apply Camera</strong>.
                </li>
              </ul>
              <p className="text-xs text-slate-500">
                No IP address is hardcoded. If the camera fails to open, the window stays open with an error banner so
                you can fix the source in Settings without restarting.
              </p>
            </div>
          </div>
        </section>

        <section id="verification" className="border-t border-slate-200 pt-12 space-y-6">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">Line Counts, Performance &amp; Verification</h2>
            <p className="mt-1 text-sm text-slate-600">
              Measured across production <code className="text-slate-900">.py</code> files excluding{' '}
              <code className="text-slate-900">backup_originals/</code>, <code className="text-slate-900">tests/</code>,
              assets, and caches. Custom gestures (<strong className="text-slate-800">Open Palm</strong> Pause/Resume,{' '}
              <strong className="text-slate-800">Thumbs-Up</strong> Confirmation,{' '}
              <strong className="text-slate-800">Peace Sign</strong> Menu,{' '}
              <strong className="text-slate-800">Pinch</strong> Select),{' '}
              <strong className="text-slate-800">AR Hand HUD (A)</strong>,{' '}
              <strong className="text-slate-800">Fingertip FX (V)</strong>, and{' '}
              <strong className="text-slate-800">One-Euro Smoothing</strong> can be tuned via{' '}
              <strong className="text-slate-800">Calibrate [K]</strong>.
            </p>
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-5 py-3 font-semibold">Codebase</th>
                  <th className="px-5 py-3 font-semibold text-right">Physical Lines</th>
                  <th className="px-5 py-3 font-semibold text-right">Non-Empty / Non-Comment</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {LINE_COUNTS.map((row) => (
                  <tr key={row.project} className={row.strong ? 'bg-slate-50 font-semibold text-slate-900' : 'text-slate-700'}>
                    <td className="px-5 py-3">{row.project}</td>
                    <td className="px-5 py-3 text-right font-mono tabular-nums">{row.physical}</td>
                    <td className="px-5 py-3 text-right font-mono tabular-nums">{row.code}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-5 py-3 font-semibold">Screen (1280×720 Synthetic AVI, CPU)</th>
                  <th className="px-5 py-3 font-semibold text-right">v2 Baseline</th>
                  <th className="px-5 py-3 font-semibold text-right">v3 Measured</th>
                  <th className="px-5 py-3 font-semibold">Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {BENCHMARKS.map((row) => (
                  <tr key={row.screen} className="text-slate-700">
                    <td className="px-5 py-3 font-medium text-slate-900">{row.screen}</td>
                    <td className="px-5 py-3 text-right font-mono tabular-nums">{row.before}</td>
                    <td className="px-5 py-3 text-right font-mono tabular-nums font-semibold text-slate-900">{row.after}</td>
                    <td className="px-5 py-3 text-xs text-slate-500">{row.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-6 text-xs text-slate-500">
          <span>Combined Camera Studio · MIT License · Attribution preserved in THIRD_PARTY_NOTICES.md</span>
          <span>10/10 automated unit &amp; integration tests passed (headless synthetic 1280×720 AVI)</span>
        </div>
      </footer>
    </div>
  );
}

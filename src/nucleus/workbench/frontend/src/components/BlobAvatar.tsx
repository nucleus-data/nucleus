/**
 * BlobAvatar — animated iridescent gradient orb for the AI Copilot card.
 *
 * Renders a small circular "blob" with a blue/purple/cyan animated gradient,
 * matching the reference image's Copilot avatar.
 *
 * Per founder visual reference (Editorial Hero v0.2).
 */

interface Props {
  size?: number;
}

export default function BlobAvatar({ size = 36 }: Props) {
  return (
    <div
      className="blob-orb"
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: 'conic-gradient(from 200deg, #4F75FF, #7C3AED, #06B6D4, #10B981, #4F75FF)',
        boxShadow: '0 0 14px rgba(79, 117, 255, 0.4), 0 0 28px rgba(124, 58, 237, 0.2)',
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        position: 'relative',
      }}
      aria-hidden="true"
    >
      {/* Inner highlight */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          borderRadius: '50%',
          background: 'radial-gradient(circle at 35% 35%, rgba(255,255,255,0.35) 0%, transparent 60%)',
          pointerEvents: 'none',
        }}
      />
    </div>
  );
}

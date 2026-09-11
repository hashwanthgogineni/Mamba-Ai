// src/lib/gameDevTips.ts
// Game development tips shown while a game is being generated.

export interface GameDevTip {
  category: string;
  text: string;
}

export const GAME_DEV_TIPS: GameDevTip[] = [
  // ---------- Game feel ----------
  { category: "Game feel", text: "Add a few frames of hit-stop when something takes damage. Freezing time briefly makes an impact land harder than any particle effect." },
  { category: "Game feel", text: "Let the player jump for ~100ms after walking off a ledge. It's called coyote time, and nobody notices it except when it's missing." },
  { category: "Game feel", text: "Buffer the jump input. If they press jump just before landing, queue it instead of dropping it." },
  { category: "Game feel", text: "Make falling faster than rising. A higher gravity on the way down makes jumps feel snappy instead of floaty." },
  { category: "Game feel", text: "Screen shake should be short and small. Two hundred milliseconds at a few pixels reads as impact; anything longer reads as a bug." },
  { category: "Game feel", text: "Scale a collectible up briefly before it disappears. A 150ms pop sells the pickup better than a sound alone." },
  { category: "Game feel", text: "Give the player character a squash on landing and a stretch on takeoff. Two lines of scale code, enormous payoff." },
  { category: "Game feel", text: "Delay the camera slightly behind the player. Perfect tracking feels rigid; a little lag feels alive." },
  { category: "Game feel", text: "Flash a sprite white for one frame when it's hit. It's the cheapest damage feedback that exists." },
  { category: "Game feel", text: "Never move the camera and the player at the same speed during a dash. Let the camera catch up." },
  { category: "Game feel", text: "Round positions to whole pixels when rendering pixel art, or everything shimmers as it moves." },
  { category: "Game feel", text: "Add a tiny bit of input acceleration, not instant max speed — unless you're making a precision platformer, where instant is correct." },
  { category: "Game feel", text: "Particles don't need physics. Spawn them, move them in a straight line, fade them out, delete them." },
  { category: "Game feel", text: "When a projectile spawns, push it slightly ahead of the barrel. Bullets emerging from inside the shooter look wrong." },
  { category: "Game feel", text: "Vary pitch on repeated sounds by a few percent. Identical sounds in a row sound mechanical." },

  // ---------- Physics & movement ----------
  { category: "Physics", text: "Multiply movement by delta time, never by frame count. Otherwise your game runs at double speed on a 120Hz monitor." },
  { category: "Physics", text: "Cap delta time at about 0.1 seconds. When a tab regains focus, an uncapped delta teleports everything through walls." },
  { category: "Physics", text: "Resolve collisions on one axis at a time. Moving both at once is where 'stuck on the corner of a platform' comes from." },
  { category: "Physics", text: "Make the player's collision box slightly smaller than the sprite. Forgiving hitboxes feel fair; accurate ones feel cheap." },
  { category: "Physics", text: "Make enemy hitboxes slightly larger than their sprite for the player's attacks. Generous in the player's favour, both ways." },
  { category: "Physics", text: "Clamp maximum fall speed. Without it, a long drop becomes a tunnelling bug." },
  { category: "Physics", text: "Store velocity separately from position. Mutating position directly makes every physics interaction harder to reason about." },
  { category: "Physics", text: "Axis-aligned bounding boxes solve 90% of 2D collision. Reach for anything fancier only when they demonstrably fail." },
  { category: "Physics", text: "Check for a ground contact by casting a short ray downward, not by testing whether vertical velocity is zero." },
  { category: "Physics", text: "Apply friction only when the player isn't pressing a direction. Applying it always makes controls feel like ice in reverse." },

  // ---------- Architecture & code ----------
  { category: "Architecture", text: "Separate update from render. Anything that draws inside update logic will fight you the moment you add a pause menu." },
  { category: "Architecture", text: "Keep a single source of truth for game state. Two places tracking score is two places that can disagree." },
  { category: "Architecture", text: "A finite state machine for the player — idle, running, jumping, falling, hurt — prevents almost every 'can jump while dying' bug." },
  { category: "Architecture", text: "Don't delete entities mid-loop. Mark them dead, then sweep at the end of the frame." },
  { category: "Architecture", text: "Pool your bullets and particles. Allocating hundreds of objects per second is how you get GC stutter." },
  { category: "Architecture", text: "Put every tunable number in one config object. Balancing a game by hunting through code is misery." },
  { category: "Architecture", text: "Make the game loop pausable from day one. Retrofitting pause into a running project is always worse than you expect." },
  { category: "Architecture", text: "Keep input reading separate from input responding. It makes replays, AI control and remapping possible later." },
  { category: "Architecture", text: "A restart function that rebuilds state from scratch beats one that tries to reset fields individually." },
  { category: "Architecture", text: "Load assets before the loop starts, not on first use. A hitch the first time an enemy appears is always a load." },

  // ---------- Design ----------
  { category: "Design", text: "Teach a mechanic in a safe room before you test it in a dangerous one. Every good level is a lesson followed by an exam." },
  { category: "Design", text: "The first thirty seconds decide whether anyone plays the next thirty minutes. Spend disproportionate effort there." },
  { category: "Design", text: "If a mechanic needs a tutorial popup to explain, try redesigning it so it doesn't." },
  { category: "Design", text: "One strong verb beats five weak ones. Decide what the player mainly does, then make that thing excellent." },
  { category: "Design", text: "Difficulty should ramp in steps, not a straight line. Give the player a plateau to feel competent on before raising it again." },
  { category: "Design", text: "Put a checkpoint before the hard part, not after the easy part." },
  { category: "Design", text: "A losing player needs information about why. Deaths that feel random make people quit; deaths that feel earned make them retry." },
  { category: "Design", text: "Reward exploration with something visible before the player commits to the detour." },
  { category: "Design", text: "Give enemies a readable wind-up. A telegraph is what turns an unfair hit into a mistake the player owns." },
  { category: "Design", text: "The player's first death should happen within a couple of minutes. It sets the stakes and teaches that the game can be lost." },
  { category: "Design", text: "Design the failure state before the success state. What happens when they lose shapes the whole experience." },
  { category: "Design", text: "Constraints generate ideas. A game where you can only move left is more interesting than one where you can do anything." },
  { category: "Design", text: "If you can remove a system and the game is still fun, remove it." },
  { category: "Design", text: "Randomness that hurts the player feels unfair; randomness that helps feels lucky. Bias your dice accordingly." },
  { category: "Design", text: "Give the player a goal they can see. A visible objective on screen beats one described in text." },

  // ---------- UI & UX ----------
  { category: "UI", text: "Score should animate up to its new value, not snap. The count-up is the reward." },
  { category: "UI", text: "Put health where the action is, or make damage obvious on the character itself. Eyes don't leave the player sprite." },
  { category: "UI", text: "Every button needs a hover state, a pressed state and a disabled state. Missing states read as broken." },
  { category: "UI", text: "Show the controls on screen for the first few seconds, then fade them out." },
  { category: "UI", text: "A pause menu that dims the game behind it is instantly more readable than one drawn on top." },
  { category: "UI", text: "Font size for in-game UI should survive being viewed on a laptop at arm's length. Test it, don't assume." },
  { category: "UI", text: "Never block input during a transition without showing something is happening." },
  { category: "UI", text: "Game over screens should offer retry as the default, focused action. Make the common case one keypress." },
  { category: "UI", text: "High contrast beats pretty for anything conveying state. Save the subtle palette for decoration." },
  { category: "UI", text: "Don't rely on colour alone to signal danger. Shape and motion carry it for colourblind players too." },

  // ---------- Audio ----------
  { category: "Audio", text: "Sound is half of game feel and gets a tenth of the effort. A jump with a sound feels twice as good as one without." },
  { category: "Audio", text: "Start audio only after a user gesture. Browsers block autoplay, and a silent game usually means a blocked audio context." },
  { category: "Audio", text: "Cap concurrent sound effects. Twenty overlapping coin sounds is noise, not feedback." },
  { category: "Audio", text: "Give the player a mute control they can find in under two seconds." },
  { category: "Audio", text: "Music should duck under important sound effects, not compete with them." },
  { category: "Audio", text: "Short, dry sounds read as responsive. Long, reverberant ones read as laggy, even at the same latency." },

  // ---------- Performance ----------
  { category: "Performance", text: "Profile before optimising. The slow thing is almost never the thing you assumed." },
  { category: "Performance", text: "Batch your draw calls. Setting fill style once for fifty rectangles is much faster than setting it fifty times." },
  { category: "Performance", text: "Don't render what's off screen. A bounds check is cheaper than a draw call every single time." },
  { category: "Performance", text: "Pre-render static backgrounds to an offscreen canvas once instead of redrawing them every frame." },
  { category: "Performance", text: "Avoid allocating objects inside the game loop. Reuse vectors instead of creating new ones sixty times a second." },
  { category: "Performance", text: "requestAnimationFrame, never setInterval. The browser knows when it's ready to paint and setInterval doesn't." },
  { category: "Performance", text: "Math.sqrt is avoidable in distance checks. Compare squared distances instead." },
  { category: "Performance", text: "A spatial grid turns collision from every-pair into every-neighbour. Worth it past a few hundred entities." },

  // ---------- Process ----------
  { category: "Process", text: "Build the ugliest possible playable version first. You can't tell if a game is fun from a design document." },
  { category: "Process", text: "Grey boxes and coloured rectangles are enough to find out whether the core loop works." },
  { category: "Process", text: "Ship something small and finished rather than something large and nearly done. Finishing is a separate skill and it needs practice." },
  { category: "Process", text: "Scope is the thing that kills projects, not difficulty. Cut features early and often." },
  { category: "Process", text: "Keep a build that always runs. A broken main branch costs more than any feature is worth." },
  { category: "Process", text: "Write down the one sentence describing your game. If you can't, the design isn't finished." },
  { category: "Process", text: "Version your saves from the first release. Migrating a save format you didn't plan for is genuinely painful." },
  { category: "Process", text: "Timebox prototypes. If a mechanic isn't fun after a day of trying, it may not be the mechanic that's wrong." },

  // ---------- Playtesting ----------
  { category: "Playtesting", text: "Watch someone play without saying a word. Everything you want to explain is a design problem." },
  { category: "Playtesting", text: "Where a playtester hesitates is more useful than anything they say afterwards." },
  { category: "Playtesting", text: "Test with someone who has never seen the game. You cannot un-know your own controls." },
  { category: "Playtesting", text: "If two testers make the same mistake, it's a design flaw, not user error." },
  { category: "Playtesting", text: "Ask what they expected to happen, not whether they liked it." },
  { category: "Playtesting", text: "Record playtests if you can. You'll notice things live that you missed, and things on replay that you missed live." },

  // ---------- Polish ----------
  { category: "Polish", text: "Polish is a hundred small things, not one big one. Each is worth about one percent and they compound." },
  { category: "Polish", text: "Ease your transitions. Linear motion looks computed; eased motion looks designed." },
  { category: "Polish", text: "Add a subtle idle animation. A character that stands perfectly still looks dead." },
  { category: "Polish", text: "Stagger simultaneous animations by a few dozen milliseconds. Everything moving in perfect unison looks robotic." },
  { category: "Polish", text: "Parallax scrolling costs almost nothing and adds an immediate sense of depth." },
  { category: "Polish", text: "A trail behind a fast-moving object reads as speed better than actually increasing the speed." },
  { category: "Polish", text: "Fade in on start and fade out on death. Hard cuts feel unfinished." },
  { category: "Polish", text: "Give the title screen the same care as the gameplay. It's the first thing anyone sees." },

  // ---------- Craft ----------
  { category: "Craft", text: "Steal mechanics openly, steal aesthetics carefully. Everyone builds on what came before." },
  { category: "Craft", text: "Play the classics in your genre and take notes on what they do in the first five minutes." },
  { category: "Craft", text: "Limit your palette. Four well-chosen colours look more intentional than twenty." },
  { category: "Craft", text: "A game that runs at a locked thirty frames feels better than one that swings between sixty and forty." },
  { category: "Craft", text: "The best game idea is the one you'll still be interested in during week three." },
  { category: "Craft", text: "Name your variables for what they mean, not what they hold. `timeSinceLastJump` beats `t2`." },
];

/**
 * Returns a shuffled copy of the tips so each generation session sees them
 * in a different order and doesn't repeat one until the list is exhausted.
 */
export function shuffleTips(): GameDevTip[] {
  const out = [...GAME_DEV_TIPS];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

# Roadmap

Rough order — each step should stay playable/testable on its own.

## Done: milestone 1 — exploration + movement core
- [x] Godot 4 project skeleton, input map
- [x] Qi resource system + cultivation realm stub
- [x] Third-person movement: walk/sprint/jump
- [x] Qinggong (light-body) air-leap + glide
- [x] Procedurally streamed, unbounded terrain
- [x] Day/night cycle, Xianxia-styled sky
- [x] Qi/realm HUD

## Milestone 2 — a world worth exploring
- [x] Biome variation: pine forest, cherry grove, bamboo grove, maple
      woods and meadow biomes; mountain layer with snow caps
- [ ] More biomes: spirit-vein caves, lowland farmland
- [x] Landmarks: procedural landmark sets (pavilions, pagodas, gates, sect
      hall, bell tower...) plus a hand-dressed spawn shrine
- [x] Water: lakes fill the valleys below the water line
- [ ] Rivers and a simple swim state
- [ ] Fall damage / qi-cushioned landing (light-body cultivators should
      take less fall damage — ties into the realm system)
- [ ] Save/load player position + qi/realm state

## Milestone 3 — combat prototype
- [ ] Lock-on / target system
- [ ] Sword-qi ranged attack (spends qi)
- [ ] 1–2 enemy archetypes (a beast, a rogue cultivator) with simple AI
- [ ] Hit reactions, a health resource separate from qi
- [ ] Death/respawn flow

## Milestone 4 — cultivation progression
- [ ] Breakthrough mechanic: meditate to advance `GameState.realm`
      (currently a stub with no trigger)
- [ ] Skill/technique unlocks gated by realm
- [ ] Pills/artifacts as inventory items that boost qi or unlock techniques
- [ ] A simple stats/character screen

## Milestone 5 — world population
- [ ] NPC sects/settlements with basic schedules (using `WorldClock`)
- [ ] Quest/dialogue stub
- [ ] Spirit beasts as wildlife (non-combat first, then combat-capable)

## Art pipeline (when ready to leave placeholders behind)
- [x] Blender-baked terrain textures + splatting shader (triplanar cliffs)
- [x] Rigged male/female cultivator models + animations
      (idle/walk/run/jump/fall/glide)
- [x] Landmark set-dressing models (pagodas, gates, bridges, halls...)
- [x] Visibility ranges per prop class, MultiMesh ground cover, Godot's
      import-time mesh LODs
- [ ] Billboard impostors for far trees if draw cost becomes a problem
- [ ] Facial/hand detail and cloth simulation for the characters

## Engineering follow-ups (not urgent, note for later)
- [ ] Terrain collision uses `ConcavePolygonShape3D` (trimesh) — fine at
      current chunk counts, but if view distance grows a lot, revisit
      (heightmap-shape or greatly reduced chunk resolution for collision
      only) for physics performance
- [ ] Chunk generation currently runs on the main thread; if chunk
      pop-in becomes noticeable, move generation to a worker thread /
      `WorkerThreadPool`

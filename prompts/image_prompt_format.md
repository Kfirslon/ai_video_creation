# Image prompt format (reference)

Each `image_prompt` in the scene pack should follow this structure. Used by Gemini's image API (Nano Banana / `gemini-2.5-flash-image-preview`).

```
Pixar-style 3D cinematic render of [CHARACTER A description with full head + clothing + expression], [CHARACTER B description if present], [environment description], [emotion / atmosphere], [camera angle], [lighting], vertical 9:16 composition, ultra detailed, consistent character design.
```

Example (retro tech-head style):
```
Pixar-style 3D cinematic render of a Gameboy-headed child wearing denim overalls crying on a suburban sidewalk, a sleek 4K Security Camera-headed man in a black security suit standing beside him shrugging arrogantly, frustrated atmosphere, bright cinematic daylight, wide camera angle, vertical 9:16 composition, ultra detailed, consistent character design.
```

## Why every prompt ends with the same suffix
- `vertical 9:16 composition` — locks aspect ratio for TikTok/Reels.
- `ultra detailed` — pushes the model toward higher fidelity.
- `consistent character design` — primes the model that this is part of a series; helps when paired with a reference image.

## Character consistency strategy
- Scene 1 is generated with no reference image.
- Scenes 2–8 are generated with Scene 1's PNG passed as a reference image to the Gemini image API.
- The prompt repeats the full character description ("the strawberry-headed mother in her pink sweater") rather than relying on pronouns.

This combination — explicit description + reference image — is the strongest free-tier approach to keeping characters identical across shots.

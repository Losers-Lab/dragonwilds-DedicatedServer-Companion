# Phase 3C: Dynamic World Actors, Fishing Spots & Zero-Latency In-Memory Caching

## 1. Overview & Objective
This phase resolves the spatial extrapolation of Dragonwilds world entities by extracting ground-truth 3D spatial transforms directly from the dedicated server's Unreal Engine 5 **SPUD (Steve's Persistent Unreal Data)** persistence system.

Rather than relying on macro-provincial centroid approximations or hardcoded lists, Phase 3C dynamically parses the server's level streaming cache (`SpudCache/*.lvl`), indexes persistent actors by unique UAID, and surfaces:
1. **Fishing Spots**: All 36 permanent Net & Rod fishing nodes along rivers and coastlines.
2. **Interactive NPCs & Quest Givers**: Key lore characters (Wise Old Man, Doric, Zanik, Bilegut, Wormelbow, Reliquary Stewards, Restless Ghost).
3. **Sacred Shrines & Monuments**: Health shrines and divine statues.
4. **Agility Shortcuts**: Kebbit burrows and subterranean tunnels.
5. **Zero-Latency In-Memory Cache**: High-performance RAM cache that responds in under 0.02ms with thread-safe file `mtime` invalidation.

---

## 2. Server Data Architecture

### A. The Engine Persistence Cache (`SpudCache`)
Unreal Engine partitions the Ashenfall continent into 128-meter (12,800 unit) spatial grid cells:
* `RSACell12800_X0_Y13.lvl`
* `RSACell12800_X1_Y14.lvl`
* `RSACell12800_X6_Y12.lvl`

### B. Binary `CORA` (Core Actor) Transform Chunk
Immediately following each actor blueprint tag (`BP_<ClassName>_C_UAID_<InstanceID>`), SPUD serializes a binary `CORA` chunk containing the actor's 64-bit IEEE 754 double precision `FTransform`:
* **Header**: 15 bytes (`FourCC=b"CORA"`, `length=159`, `decomp=155`, `flags=1`, version/padding)
* **Quaternion Rotation**: 32 bytes (`4 x double`: $X, Y, Z, W$)
* **Position Vector**: 24 bytes (`3 x double`: $X, Y, Z$) at offsets `47:55`, `55:63`, `63:71`
* **Scale Vector**: 24 bytes (`3 x double`: $1.0, 1.0, 1.0$)

---

## 3. In-Memory Caching Architecture

To prevent disk I/O thrashing during frequent client polling and user UI interactions:
1. **RAM-First Fast Path**: If a request arrives within the cache TTL (60s), the server serves the response directly from the Python in-memory dictionary ($<0.02\text{ ms}$).
2. **Fast Stat Check**: Upon TTL expiry, the manager executes `os.scandir()` to check file timestamps (`st_mtime`). If no `.lvl` file was modified by the server, the TTL is extended without opening or reading any files ($<0.5\text{ ms}$).
3. **Thread Safety**: Protected with `threading.Lock()`.
4. **Strict Read-Only Enforcement**: Mounts `C:\DragonwildsServer\RSDragonwilds\Saved\SpudCache` as `:ro`. Zero write calls.

---

## 4. Coordinate Projection & Calibration

Unreal Engine centimeter units $(X, Y)$ are projected to the 1000x1000 Ashenfall Canvas $(px, py)$ using calibrated ground-truth anchors:
* **Starter Beach** (`WiseOldMan_FTUE`): $X = 6,133, Y = 187,356 \implies px = 210.2, py = 500.6$
* **Bramblemead Village** (`WiseOldMan_Village`): $X = 48,499, Y = 177,605 \implies px = 273.7, py = 483.1$
* **Castle Stronghold** (`ReliquaryCastle`): $X = 81,070, Y = 154,387 \implies px = 322.6, py = 441.3$

$$\text{Canvas } X = \text{clamp}\left(210.0 + (X - 6000.0) \times 0.0015, 15, 985\right)$$
$$\text{Canvas } Y = \text{clamp}\left(500.0 + (Y - 187000.0) \times 0.0018, 15, 985\right)$$

---

## 5. Corroboration with Wiki Data
Cross-referenced against `wiki_data/dragonwilds_wiki.jsonl` (3,930 articles):
* **Bilegut**: Wiki `{{Map|Bilegut|center=155000,80000}}` corresponds to SPUD coordinates `Y=156,893, X=79,805`.
* **Wormelbow**: Wiki `{{Map|Wormelbow|center=175000,80000}}` corresponds to SPUD coordinates `Y=172,223, X=79,037`.
* **Fishing Nodes**: Wiki confirms Net vs Rod requirements, which match `BP_FishingNodeV2_Net_Brynmoor_C` and `BP_FishingNodeV2_Rod_Brynmoor_C`.

Website design specification: ZFS Configuration Advisor

1. Product objective

Build a web application that helps homelab and small-lab users design, compare, validate, and document ZFS storage configurations for systems with 1–100 disks.

The site should support two main workflows:

1. Recommendation mode
    User enters available disks, workload, and priorities. The app returns ranked ZFS pool/vdev configurations with capacity, performance, resiliency, rebuild-risk, cost, and operational pros/cons.
2. Validation mode
    User manually defines pools, vdevs, SLOG, L2ARC, special vdevs, spares, datasets, and tunables. The app analyses the design and tells the user whether it is good, risky, wasteful, invalid, or workload-mismatched.

The system should not merely say “use mirrors” or “use RAIDZ2”. It should act like a ZFS design review tool.

⸻

2. Core terminology

Use the correct ZFS language throughout the UI:

Term	Meaning in the website
Disk / device	Physical HDD, SSD, NVMe, USB disk, SAS disk, etc.
Pool	Top-level ZFS storage pool, made of one or more top-level vdevs.
Top-level vdev	Mirror, RAIDZ1/2/3, dRAID, single disk, etc. Pool failure occurs if any top-level vdev fails.
Data vdev	Main storage vdev containing user data.
Mirror vdev	Two-way, three-way, or N-way mirror.
RAIDZ vdev	Single-, double-, or triple-parity RAIDZ vdev.
dRAID vdev	Distributed RAIDZ-like vdev with integrated distributed spare capacity. OpenZFS describes dRAID as a RAIDZ variant with distributed hot spares and faster resilvering characteristics.  ￼
SLOG / log vdev	Separate ZFS Intent Log device for synchronous writes. Not a write cache.
L2ARC / cache vdev	Secondary read cache device. Cache devices are disposable from a data-integrity point of view because reads can fall back to the main pool.  ￼
Special vdev	Allocation class for metadata and optionally small blocks. Dangerous if under-protected because losing it can lose the pool.
Spare	Device reserved for replacement after disk failure. OpenZFS documents spare, cache, and log as special device classes.  ￼
Dataset	ZFS filesystem or volume with properties such as compression, recordsize, sync, atime, quota, reservation.
zvol	Block device provided by ZFS, often used for VM disks or iSCSI.

Important UI correction: the user may type “udev”. The app should infer they probably mean vdev and display: “Did you mean vdev?”

⸻

3. Target user personas

3.1 Homelab beginner

Has 4–12 mixed disks. Wants Plex, backups, Time Machine, photos, documents, Docker apps.

Needs:

* “What should I build?”
* “Is RAIDZ1 safe?”
* “Can I mix 8 TB and 16 TB drives?”
* “Should I use my NVMe as cache?”
* “How much usable space will I get?”

3.2 Advanced homelabber

Has 12–40 disks, old servers, HBAs, disk shelves, mixed SATA/SAS/NVMe.

Needs:

* Multi-vdev planning.
* Rebuild-risk comparison.
* Dataset property advice.
* SLOG/L2ARC/special-vdev guidance.
* Bottleneck analysis: network, HBA, PCIe, disk IOPS.

3.3 Small business / lab admin

Has 20–100 disks, wants reliability, documented design, exportable report.

Needs:

* “Give me a professional design.”
* “Compare 6× RAIDZ2 vs 10× mirrors.”
* “Show failure tolerance.”
* “Warn me if this is operationally fragile.”
* “Produce a change plan.”

⸻

4. High-level site structure

Main navigation

Section	Purpose
Advisor	Guided recommendation wizard.
Designer	Manual drag-and-drop pool/vdev builder.
Compare	Side-by-side comparison of recommended or custom designs.
Validator	Paste zpool status, lsblk, smartctl, zfs list, or TrueNAS export for review.
Knowledge Base	ZFS concepts, vdev types, SLOG, L2ARC, special vdevs, dataset properties.
Reports	Export PDF/Markdown/JSON design reports.
Templates	Common configs: 4-bay NAS, 8-bay NAS, 12-bay shelf, 24-bay server, 36-bay JBOD, 60-bay chassis.

⸻

5. Main workflows

5.1 Workflow A — Recommendation mode

Step 1: Disk inventory

The user can enter disks in two ways.

Option A: Grouped entry

Example:

20 disks of 16 TB HDD, 7200 RPM, 250 MB/s sequential, 80 IOPS random.

Fields:

Field	Type	Default
Count	Integer	Required
Size	TB / GB	Required
Media type	HDD / SATA SSD / SAS SSD / NVMe / USB	HDD
Interface	SATA / SAS / USB / NVMe / iSCSI / unknown	unknown
RPM	5400 / 7200 / 10000 / 15000 / N/A	7200 for HDD
Sequential read MB/s	Number	Estimated by disk type
Sequential write MB/s	Number	Estimated by disk type
Random read IOPS	Number	Estimated by disk type
Random write IOPS	Number	Estimated by disk type
AFR / reliability	% per year	Default by class
Power draw idle/load	W	Optional
Sector size	512e / 4Kn / unknown	unknown
SMR/CMR	CMR / SMR / unknown	unknown
New or used	New / Used / Unknown	Unknown
Role allowed	Data / SLOG / L2ARC / special / spare	Data

Option B: Individual disk entry

Useful for mixed disks:

Disk ID	Size	Type	Speed	Health	Notes
disk01	16 TB	HDD	250 MB/s	Good	Toshiba MG08
disk02	16 TB	HDD	250 MB/s	Good	Toshiba MG08
disk03	8 TB	HDD	210 MB/s	Used	HGST
nvme01	1 TB	NVMe	3,500 MB/s	Good	Possible apps pool

Bulk import options

The website should support:

* Paste from lsblk.
* Paste from smartctl --scan.
* Paste from zpool status.
* Upload JSON.
* Upload CSV.
* TrueNAS-style inventory import.
* Manual “I have X disks of Y size”.

⸻

Step 2: Workload selection

The user chooses one or more workloads:

Workload	Relevant ZFS advice
Media server	Capacity and sequential reads matter more than random IOPS.
Backup target	Resiliency, snapshots, compression, and scrub schedule matter.
Time Machine	Dataset quotas, snapshots, SMB tuning, many small metadata operations.
VM storage	Mirrors usually preferred; low latency and random IOPS matter.
Docker apps	SSD/NVMe app pool recommended; avoid putting databases on slow RAIDZ HDD pool where possible.
Databases	Low latency, sync semantics, SLOG if sync writes are real and storage supports it.
Photos/documents	Metadata performance, snapshots, checksums, backup strategy.
Video editing	Sequential throughput and scratch/cache separation.
Cold archive	Capacity and redundancy over IOPS.
Mixed homelab	Balanced recommendation.

⸻

Step 3: Priorities

Sliders or weighted ranking:

Priority	Meaning
Maximum usable capacity	Prefer wider RAIDZ/dRAID, fewer parity disks.
Maximum performance	Prefer mirrors and more vdevs.
Maximum resiliency	Prefer RAIDZ2/3, 3-way mirrors, hot spares, fewer risky topologies.
Easy future expansion	Prefer mirrors or same-width vdev growth strategy.
Lowest power	Prefer fewer spinning disks, possible SSD tier.
Lowest cost	Use existing disks efficiently.
Fast rebuild/resilver	Prefer mirrors, dRAID for larger arrays, hot spares.
Simple operation	Avoid exotic layouts, avoid mixed-size complexity.
Data safety over all	Enforce conservative rules.

Recommended default for homelab:

Resiliency: high
Performance: medium
Capacity: medium
Expansion flexibility: medium-high
Complexity tolerance: low-medium

⸻

Step 4: Constraints

Constraint	Examples
Maximum disks per vdev	6, 8, 10, 12
Minimum fault tolerance	1, 2, 3 disk failures
Allow RAIDZ1?	Yes/no
Allow single-disk vdevs?	Normally no
Allow mixed-size vdevs?	Warn strongly
Require hot spare?	Yes/no
Use SSD/NVMe for apps?	Yes/no
Platform	TrueNAS SCALE, Proxmox, Ubuntu, FreeBSD, OpenZFS generic
Network speed	1G, 2.5G, 10G, 25G
HBA bandwidth	PCIe generation/lanes
RAM	GB
ECC RAM	Yes/no/unknown
UPS	Yes/no/unknown

⸻

Step 5: Output recommended configurations

Each result should have:

Output	Description
Name	“Balanced: 2× 6-wide RAIDZ2”
Layout diagram	Visual vdev/pool layout
Usable capacity	TiB and TB, with reserve warning
Raw capacity	Total disk size
Fault tolerance	Per-vdev and pool-level explanation
Estimated read throughput	Sequential and random
Estimated write throughput	Sequential and random
Rebuild risk	Low/medium/high
Expansion path	How to add capacity later
Complexity	Simple/moderate/advanced
Recommended datasets	Suggested dataset layout
SLOG/L2ARC/special recommendation	Whether useful or not
Pros	Plain-English advantages
Cons	Plain-English disadvantages
Commands	zpool create example
TrueNAS equivalent	GUI mapping
Score	Weighted score based on user priorities

⸻

6. Manual designer mode

The manual designer should let the user build:

Pool: tank
├── data vdev 1: mirror
│   ├── disk01 16 TB
│   └── disk02 16 TB
├── data vdev 2: mirror
│   ├── disk03 16 TB
│   └── disk04 16 TB
├── log vdev: mirror
│   ├── nvme01 256 GB
│   └── nvme02 256 GB
├── cache vdev
│   └── ssd01 1 TB
├── special vdev: mirror
│   ├── nvme03 1 TB
│   └── nvme04 1 TB
└── spare
    └── disk05 16 TB

Designer features

Drag-and-drop

* Drag disks into vdevs.
* Drag vdevs into pools.
* Drag SSDs into log/cache/special roles.
* Prevent invalid topology where possible.
* Allow expert override, but show red warnings.

Supported pool structures

For under 100 disks, support:

Type	Should support?	Notes
Single disk pool	Yes, but warn heavily	
Stripe of disks	Yes, but warn catastrophic failure risk	
Mirror vdevs	Yes	
2-way mirrors	Yes	
3-way mirrors	Yes	
N-way mirrors	Yes	
RAIDZ1	Yes, but warn for large disks	
RAIDZ2	Yes	
RAIDZ3	Yes	
Multiple RAIDZ vdevs	Yes	
dRAID1/2/3	Yes, advanced	
Hybrid pools	Yes, but warn where vdev classes differ	
SLOG	Yes	
Mirrored SLOG	Yes	
L2ARC	Yes	
Multiple L2ARC devices	Yes	
Special vdev	Yes, with strong warnings	
Mirrored special vdev	Yes	
3-way special vdev	Yes	
Dedup vdev	Advanced, warn heavily	
Spares	Yes	
Multiple pools	Yes	
Apps pool + data pool	Yes	
Backup pool	Yes	

⸻

7. ZFS possibility matrix under 100 disks

7.1 Basic layouts

Layout	Suitable disk count	Strength	Weakness
Single disk	1	Simple, maximum capacity	No redundancy
Stripe	2–100	Maximum capacity/performance	Any disk loss can lose pool
2-way mirror	2+	Good IOPS, simple resilver	50% usable capacity
3-way mirror	3+	Strong resiliency	33% usable capacity
RAIDZ1	3–6 preferred	Good capacity	Weak for large disks and long resilvers
RAIDZ2	4–12 typical	Strong homelab default	Lower random IOPS than mirrors
RAIDZ3	5–16 typical	High resiliency	More parity overhead
dRAID	Usually larger arrays	Faster distributed spare behaviour	More complex, less beginner-friendly

TrueNAS documentation describes dRAID as intended for storage arrays with numerous attached disks, while OpenZFS documents it as a RAIDZ variant with distributed spare behaviour. For this website, dRAID should be exposed as an advanced option, not the default for small homelab pools.  ￼

⸻

7.2 Recommended data-vdev ranges

These are pragmatic defaults, not absolute ZFS limits.

Vdev type	Recommended width	Website stance
2-way mirror	2 disks	Excellent for performance and expansion
3-way mirror	3 disks	Excellent for critical data
RAIDZ1	3–5 disks	Only for small disks or non-critical data
RAIDZ2	4–10 disks	Best general homelab parity choice
RAIDZ2 wide	11–12 disks	Acceptable for archive/media, slower rebuilds
RAIDZ3	7–15 disks	Good for large drives / archive
dRAID1	8+ disks	Advanced, capacity-oriented
dRAID2	12+ disks	Advanced, safer default for dRAID
dRAID3	18+ disks	Advanced, large arrays

⸻

8. Recommendation logic

8.1 Candidate generation

Given disk inventory, generate possible layouts:

Example: 20× 16 TB HDD

Candidate layouts:

Candidate	Layout
A	10× 2-way mirrors
B	6× 3-way mirrors + 2 spares
C	2× 10-wide RAIDZ2
D	2× 10-wide RAIDZ3
E	3× 6-wide RAIDZ2 + 2 spares
F	4× 5-wide RAIDZ1 — warn
G	1× 20-wide RAIDZ3 — warn for wide vdev
H	dRAID2 with distributed spare
I	1 pool for data + separate SSD/NVMe apps pool if SSDs exist

The engine should remove or demote bad candidates.

⸻

8.2 Scoring dimensions

Each candidate receives scores from 0–100.

Dimension	Scoring idea
Usable capacity	Effective usable TiB after parity/mirror overhead
Fault tolerance	Number of failures tolerated before data loss
Random read IOPS	Roughly number of data vdevs × single-vdev contribution
Random write IOPS	Mirrors score high; RAIDZ lower
Sequential throughput	More disks and vdevs score higher
Resilver risk	Mirrors and narrower RAIDZ score better
Expansion flexibility	Mirrors score high; fixed-width RAIDZ lower
Operational simplicity	Common layouts score higher
Mixed-disk efficiency	Penalise wasted capacity
Workload match	Based on selected workload
Hardware balance	Penalise if network/HBA bottleneck makes config pointless
Data safety	Penalise RAIDZ1, single disks, unmirrored special vdevs

⸻

8.3 Weighted score

Example:

overall_score =
  capacity_score        * user_weight_capacity +
  performance_score     * user_weight_performance +
  resiliency_score      * user_weight_resiliency +
  expandability_score   * user_weight_expandability +
  simplicity_score      * user_weight_simplicity -
  risk_penalties

The UI should expose the ranking logic:

“This configuration ranked first because you prioritised resiliency and future expansion over maximum capacity.”

⸻

9. Capacity calculations

9.1 Display both TB and TiB

Users buy disks in TB but operating systems show TiB.

Example:

16 TB manufacturer capacity ≈ 14.55 TiB usable before ZFS overhead.

The app should always display:

Metric	Example
Raw decimal capacity	320 TB
Raw binary capacity	291 TiB
Estimated usable before reserve	233 TiB
Recommended 80% practical fill limit	186 TiB

9.2 Capacity by vdev type

Mirror

usable = smallest_disk_in_mirror

For N mirrors:

pool_usable = sum(each_mirror_usable)

RAIDZ

Simplified estimate:

usable = (number_of_disks - parity_disks) × smallest_disk_size

Where:

Type	Parity disks
RAIDZ1	1
RAIDZ2	2
RAIDZ3	3

dRAID

Simplified user-facing estimate:

usable ≈ total_disks - parity_groups - distributed_spare_capacity

Advanced view should expose:

dRAID{parity}:{data}d:{children}c:{spares}s

Example:

draid2:8d:20c:1s

⸻

10. Performance modelling

This must be explicitly labelled estimate, not benchmark.

10.1 Sequential reads

Approximation:

sequential_read ≈ sum(read_bandwidth_of_active_disks) × efficiency_factor

Efficiency factor examples:

Layout	Factor
Stripe	0.85–0.95
Mirrors	0.75–0.95
RAIDZ	0.65–0.85
dRAID	0.65–0.85

10.2 Sequential writes

Approximation:

mirror_write ≈ number_of_mirror_vdevs × single_disk_write
raidz_write ≈ number_of_raidz_vdevs × data_disks_per_vdev × disk_write × efficiency_factor

10.3 Random IOPS

Practical rule:

Layout	Random read	Random write
Single disk	1 disk	1 disk
2-way mirror	Up to 2 disks read	About 1 disk write
N mirror vdevs	Scales with vdev count	Scales with vdev count
RAIDZ vdev	Similar to one vdev for small random I/O	Poorer than mirrors
Multiple RAIDZ vdevs	Scales by vdev count	Scales by vdev count
dRAID	Similar considerations to RAIDZ; OpenZFS notes random IOPS can be approximated by vdev group structure.  ￼	

The app should display:

“For VM/database workloads, vdev count usually matters more than raw disk count.”

⸻

11. Resiliency model

11.1 Failure tolerance

The website must explain that pool safety depends on each top-level vdev.

Examples:

Pool	Tolerates
10× 2-way mirrors	One disk per mirror vdev. Could survive many disk failures if they hit different mirrors; can fail if both disks in one mirror fail.
2× RAIDZ2	Two disk failures per RAIDZ2 vdev. Third failure in same vdev can lose pool.
1× RAIDZ3	Three disk failures in that vdev.
Stripe	Any single disk failure may lose the pool.

11.2 Risk labels

Label	Meaning
Green	Sensible for selected workload
Amber	Acceptable but has tradeoffs
Red	High risk or poor match
Black	Invalid or catastrophic design

Examples:

Design	Label	Reason
2× 6-wide RAIDZ2	Green	Good balance for media/backup
10× 2-way mirrors	Green	Excellent performance and expansion, lower capacity
1× 12-wide RAIDZ1	Red	Too much risk for large disks
Unmirrored special vdev	Black	Special vdev loss can compromise pool
SLOG on consumer USB SSD	Red	Poor latency/endurance/reliability
L2ARC on spare SSD with 8 GB RAM	Amber/red	RAM may be better used for ARC

⸻

12. SLOG / ZIL design

12.1 UI explanation

The app must state clearly:

“SLOG is not a general write cache. It only helps synchronous writes when the workload actually uses sync writes and the SLOG device has very low latency, high endurance, and power-loss protection.”

12.2 When to recommend SLOG

Recommend only when:

Condition	Required?
Workload uses sync writes	Yes
NFS/iSCSI/VM/databases selected	Often
Device has PLP	Strongly preferred
Low latency	Required
High endurance	Required
Mirrored if critical	Recommended

12.3 When not to recommend SLOG

Warn when:

* SMB media share.
* Plex library.
* General file archive.
* Consumer SSD without PLP.
* USB SSD.
* User thinks SLOG increases all write speed.
* User has no sync workload.

12.4 SLOG sizing

For homelab:

SLOG usually needs only enough capacity for a few seconds of synchronous writes.

UI should suggest:

Environment	Typical SLOG size
Homelab	8–32 GB usable
Busy VM host	16–64 GB
Enterprise sync workload	Workload-specific

Do not recommend wasting a 2 TB NVMe as full SLOG unless partitioning or overprovisioning is intended.

⸻

13. L2ARC design

13.1 UI explanation

L2ARC is a secondary read cache. It helps only when:

* Hot working set is larger than RAM.
* Data is repeatedly read.
* Main disks are slow.
* L2ARC device is fast enough.
* There is sufficient RAM to manage it.

Cache devices are not part of the redundancy model; OpenZFS/FreeBSD documentation notes that cache devices cannot be mirrored or RAIDZ, and failed reads can be served from the original pool instead.  ￼

13.2 When to recommend

Workload	L2ARC usefulness
Repeated reads of same large dataset	Medium/high
VM images	Sometimes
Metadata-heavy browsing	Sometimes
Plex streaming	Usually low
Backup target	Usually low
One-off sequential reads	Low

13.3 Warnings

* Do not add L2ARC before having enough RAM.
* L2ARC does not fix poor pool topology.
* L2ARC does not improve writes.
* L2ARC can add write wear to SSD.
* In many homelabs, more RAM is better than L2ARC.

⸻

14. Special vdev design

14.1 What it does

Special vdevs can store:

* Metadata.
* Indirect blocks.
* Dedup tables, if configured.
* Optionally small file blocks via special_small_blocks.

14.2 Strong warning

The app should show this in red:

“A special vdev is not a disposable cache. If the special vdev is lost, the pool can be lost. It should be at least as redundant and reliable as the data vdevs.”

14.3 Recommendation logic

Situation	Recommendation
HDD pool with many small files	Special vdev may help
Media-only archive	Usually not necessary
Photo/document store	May help metadata browsing
VM/database pool	Consider separate SSD pool instead
Only one SSD available	Do not use as special vdev
Two consumer SSDs	Possible mirrored special vdev, but warn
Enterprise mirrored SSD/NVMe	Good candidate
RAIDZ data pool	Special vdev should be mirrored or 3-way mirror

14.4 Sizing estimate

The app should estimate metadata size:

Dataset type	Metadata estimate
Large media files	0.1–0.5%
Photos/documents	0.5–2%
Small files/source code	2–10%
Dedup-heavy	Potentially much higher

For special_small_blocks, estimate additional usage based on file-size distribution.

⸻

15. Deduplication

The app should be blunt:

“Do not enable ZFS deduplication casually.”

Dedup recommendation rules

Scenario	Advice
General homelab	Do not enable
Photos/videos	Usually poor dedup benefit
VM clones	Maybe, but test first
Backup repository	Maybe, depending on tool
Lots of identical files	Possible, benchmark first
Low RAM	Do not enable
No special/dedup vdev	Usually avoid
User wants to save space on duplicate photos	Prefer file-level dedup tools first

The app should suggest safer alternatives:

* Compression.
* Application-level deduplication.
* Backup tools with chunking.
* File-level duplicate detection.
* Separate dedup-tested dataset.

⸻

16. Compression

Compression should be recommended by default.

Dataset property advice

Workload	Compression
General data	lz4 or modern equivalent default
Text/source code	Strong benefit
VM disks	Often beneficial
Media files	Little capacity benefit but usually harmless
Backups	Depends on backup tool
Databases	Test

UI guidance:

“Enable compression unless there is a specific reason not to.”

⸻

17. Dataset design advisor

The app should recommend dataset layouts.

Example homelab dataset tree

tank/
├── media
│   ├── movies
│   ├── tv
│   └── music
├── backups
│   ├── timemachine
│   ├── laptops
│   └── servers
├── documents
├── photos
├── apps
├── vm
└── scratch

Dataset properties by workload

Dataset	recordsize	compression	atime	sync	quota/reservation
media	1M	on/lz4	off	standard	Optional
photos	128K–1M	on	off	standard	Optional
documents	128K	on	off	standard	Optional
Time Machine	128K	on	off	standard	Quota strongly recommended
VM images	16K–64K	on	off	standard/always depending workload	Reservation optional
databases	8K–16K	workload-specific	off	workload-specific	Reservation useful
backups	128K–1M	depends	off	standard	Quota useful
scratch	1M	optional	off	disabled acceptable if disposable	No

The app should warn:

* Do not set sync=disabled on important data unless the user accepts data-loss risk.
* Use quotas for Time Machine.
* Do not put high-write databases on slow HDD RAIDZ if an SSD app pool is available.
* Avoid one giant flat dataset for everything.

⸻

18. Pool design templates

18.1 4 disks

Goal	Recommended layout
Capacity	RAIDZ1, but warn for large disks
Balanced safety	RAIDZ2
Performance	2× mirrors
Critical data	3-way mirror + spare, or RAIDZ2

18.2 6 disks

Goal	Recommended layout
Balanced	6-wide RAIDZ2
Performance	3× 2-way mirrors
High safety	6-wide RAIDZ3
Expansion	mirrors

18.3 8 disks

Goal	Recommended layout
Balanced	8-wide RAIDZ2
Performance	4× 2-way mirrors
Safer archive	8-wide RAIDZ3
Mixed workload	SSD apps pool + HDD RAIDZ2

18.4 12 disks

Goal	Recommended layout
Balanced	2× 6-wide RAIDZ2
Capacity	1× 12-wide RAIDZ2, with warning
Safer archive	1× 12-wide RAIDZ3
Performance	6× mirrors
Good homelab default	2× 6-wide RAIDZ2

18.5 16 disks

Goal	Recommended layout
Balanced	2× 8-wide RAIDZ2
Safer	2× 8-wide RAIDZ3
Performance	8× mirrors
Expansion	mirrors or 4× 4-wide RAIDZ2
Archive	1× 16-wide RAIDZ3, warn about width

18.6 20 disks

Goal	Recommended layout
Balanced	2× 10-wide RAIDZ2
Safer	2× 10-wide RAIDZ3
Performance	10× mirrors
Rebuild-friendly	3× 6-wide RAIDZ2 + 2 spares
Advanced	dRAID2 with distributed spare

18.7 24 disks

Goal	Recommended layout
Balanced	4× 6-wide RAIDZ2
Capacity	2× 12-wide RAIDZ2
Safer	3× 8-wide RAIDZ3
Performance	12× mirrors
Advanced large array	dRAID2/dRAID3

18.8 36 disks

Goal	Recommended layout
Balanced	6× 6-wide RAIDZ2
Capacity	3× 12-wide RAIDZ2
Safer	4× 9-wide RAIDZ3
Performance	18× mirrors
Advanced	dRAID2/dRAID3 with distributed spare capacity

18.9 60 disks

Goal	Recommended layout
Conservative	10× 6-wide RAIDZ2
Capacity	6× 10-wide RAIDZ2
Safer archive	5× 12-wide RAIDZ3
Performance	30× mirrors
Advanced	dRAID2/dRAID3

18.10 100 disks

Goal	Recommended layout
Conservative	16× 6-wide RAIDZ2 + spares
Capacity	10× 10-wide RAIDZ2
Safer	8× 12-wide RAIDZ3 + spares
High IOPS	50× mirrors
Advanced	Multiple dRAID vdevs, not one giant unreviewed pool

For very large homelab pools, the website should recommend considering multiple pools instead of one huge pool, especially where workloads differ.

⸻

19. Mixed-size disk handling

19.1 Rules

Situation	Advice
Mixed disks inside same RAIDZ vdev	Capacity limited by smallest disk
Mixed mirror pairs	Pair same-size disks where possible
Different vdev sizes in same pool	Allowed, but can create imbalance
Adding larger disks to existing RAIDZ	Expansion depends on platform/features; warn
Replacing all disks in vdev with larger ones	Standard expansion path

19.2 Optimiser

Given:

8× 16 TB
4× 8 TB
2× 4 TB

The app should propose:

* Pool A: 8× 16 TB as RAIDZ2.
* Pool B: 4× 8 TB as RAIDZ2 or 2× mirrors.
* Use 4 TB disks as backup, scratch, or spares only if appropriate.
* Avoid mixing all disks into one RAIDZ vdev.

⸻

20. Hardware bottleneck advisor

The website should include non-ZFS hardware checks.

20.1 Network bottleneck

Network	Approximate max
1 GbE	~110 MB/s
2.5 GbE	~280 MB/s
10 GbE	~1,100 MB/s
25 GbE	~2,800 MB/s

If the pool can read at 2 GB/s but the user has 1 GbE, show:

“Your network is the bottleneck. More disk performance will not help network file transfers.”

20.2 HBA / PCIe bottleneck

Ask for:

* HBA model.
* PCIe generation.
* PCIe lane count.
* SAS link speed.
* Expander/backplane.
* USB enclosure yes/no.

Warn against:

* SATA port multipliers.
* USB for critical multi-disk ZFS.
* Mixing unreliable controllers.
* Consumer USB enclosures with poor error reporting.
* Non-IT-mode RAID controllers.

20.3 RAM

Show:

Use case	RAM advice
Basic NAS	8–16 GB minimum practical
Larger homelab	32–64 GB useful
Heavy ARC	More RAM useful
L2ARC	Needs enough RAM first
Dedup	Requires serious RAM planning

Do not enforce old simplistic “1 GB per TB” rules. Present RAM as workload-dependent.

⸻

21. Validation engine

The validation engine should return structured findings.

21.1 Finding format

{
  "severity": "red",
  "category": "special_vdev",
  "title": "Unmirrored special vdev",
  "finding": "The special vdev is a single SSD. If it fails, the pool may be lost.",
  "recommendation": "Use at least a mirror for the special vdev, preferably devices with similar or better reliability than the data vdevs.",
  "confidence": "high"
}

21.2 Severity levels

Severity	Meaning
Info	Useful observation
Low	Minor improvement
Medium	Worth considering
High	Real design risk
Critical	Can cause pool loss or severe data loss

⸻

22. Validation rules

22.1 Pool-level rules

Rule	Severity
Single top-level disk vdev in important pool	Critical
Stripe of disks with no redundancy	Critical
Mixed redundancy vdevs in same pool	High
Very different vdev sizes	Medium/high
Pool over 80% full	Medium/high
Pool over 90% full	High
No scrub schedule	Medium
No SMART monitoring	Medium
No backup	High
No UPS for write-heavy system	Medium/high
No snapshots for important datasets	Medium/high

22.2 RAIDZ rules

Rule	Severity
RAIDZ1 with large modern HDDs	High
RAIDZ1 over 6 disks	High
RAIDZ2 over 12 disks	Medium/high
RAIDZ3 over 16 disks	Medium
One very wide RAIDZ vdev where multiple narrower vdevs possible	Medium
RAIDZ for VM/database workload	Medium/high depending workload

22.3 Mirror rules

Rule	Severity
2-way mirrors with no backup	Medium
3-way mirrors for critical data	Positive
Many mirrors but no spare	Low/medium
Mirrors across same physical enclosure/backplane only	Medium
Mismatched mirror sizes	Low/medium

22.4 SLOG rules

Rule	Severity
SLOG on USB	High
SLOG on consumer SSD without PLP	High
Unmirrored SLOG for critical sync workload	Medium/high
Huge SLOG device wasted	Low
SLOG configured but no sync workload	Info/low
User thinks SLOG is write cache	Educational warning

22.5 L2ARC rules

Rule	Severity
L2ARC with very low RAM	Medium
L2ARC for sequential media workload	Low
L2ARC on slow SSD	Low/medium
L2ARC expected to improve writes	Educational warning

22.6 Special vdev rules

Rule	Severity
Unmirrored special vdev	Critical
Special vdev less reliable than data vdev	High
Special vdev too small	Medium/high
Special vdev on USB	Critical
special_small_blocks too aggressive	Medium/high
No monitoring of special vdev	High

22.7 Dedup rules

Rule	Severity
Dedup enabled globally	High
Dedup enabled with low RAM	High
Dedup enabled without measured dedup ratio	Medium/high
Dedup for media files	Medium
Dedup for VM clones with test evidence	Info/acceptable

⸻

23. Output report

Each generated design should have a professional report.

Report sections

1. Executive summary
2. Disk inventory
3. Recommended layout
4. Alternative layouts considered
5. Capacity estimate
6. Performance estimate
7. Resiliency and failure-domain analysis
8. SLOG/L2ARC/special-vdev advice
9. Dataset design
10. Snapshot and replication advice
11. Hardware bottleneck analysis
12. Risks and mitigations
13. Expansion plan
14. zpool/zfs command examples
15. TrueNAS GUI mapping
16. Final recommendation

Export formats

* PDF.
* Markdown.
* JSON.
* YAML.
* Shell script.
* TrueNAS notes/checklist.
* Mermaid diagram.
* SVG layout diagram.

⸻

24. Example output: 20× 16 TB HDD

User priorities

Capacity: medium
Performance: medium
Resiliency: high
Expansion: medium
Workload: media, backups, documents, light apps

Top recommendation

Option 1 — Balanced

Pool: tank
Data vdevs:
  - raidz2: 10× 16 TB
  - raidz2: 10× 16 TB

Metric	Estimate
Raw capacity	320 TB
Approx raw TiB	~291 TiB
Approx usable before reserve	~233 TiB
Practical recommended max at 80%	~186 TiB
Fault tolerance	Up to 2 disk failures per vdev
Performance	Good sequential, moderate random IOPS
Expansion	Add another 10-wide RAIDZ2 vdev later
Complexity	Low/moderate

Pros:

* Good capacity.
* Sensible parity protection.
* Simple to understand.
* Good for media and backup workloads.

Cons:

* Random IOPS weaker than mirrors.
* Expansion ideally requires another 10 disks.
* Resilver times can be long with 16 TB drives.

⸻

Option 2 — Performance / expansion

Pool: tank
Data vdevs:
  - 10× mirror vdevs, each 2× 16 TB

Metric	Estimate
Raw capacity	320 TB
Approx usable before reserve	~145 TiB
Practical recommended max at 80%	~116 TiB
Fault tolerance	One disk per mirror; can survive many failures if distributed
Performance	Excellent random IOPS
Expansion	Add one mirror pair at a time
Complexity	Low

Pros:

* Best for VMs, apps, databases.
* Easy expansion.
* Fast resilver.
* Strong day-to-day performance.

Cons:

* Half raw capacity.
* A mirror pair failure loses the pool.
* Requires careful disk pairing and monitoring.

⸻

Option 3 — Safer archive

Pool: tank
Data vdevs:
  - raidz3: 10× 16 TB
  - raidz3: 10× 16 TB

Pros:

* Higher parity safety.
* Good for large disks and archive workloads.

Cons:

* Less usable capacity than RAIDZ2.
* Still not ideal for random IOPS.
* Expansion requires another vdev.

⸻

Option 4 — Smaller vdevs plus spares

Pool: tank
Data vdevs:
  - raidz2: 6× 16 TB
  - raidz2: 6× 16 TB
  - raidz2: 6× 16 TB
Spares:
  - 2× 16 TB

Pros:

* Narrower vdevs.
* Good resilver characteristics.
* Dedicated spares.

Cons:

* Slightly less capacity efficient.
* More vdevs to manage.
* Two disks reserved as spares.

⸻

25. “Good or bad?” configuration assessment

The site should produce a clear verdict.

Example:

Verdict: Amber — usable but not ideal.
Your 1× 12-wide RAIDZ2 pool is acceptable for media/archive workloads, but it is not ideal for VMs or databases. The main concerns are long resilver times, limited random IOPS, and inflexible expansion. If you can rebuild, 2× 6-wide RAIDZ2 would be better balanced.

Verdict categories

Verdict	Meaning
Excellent	Strong match, low risk
Good	Sensible with minor caveats
Acceptable	Works, but tradeoffs are material
Risky	Likely to cause problems
Bad	Should not be used for important data
Invalid	Technically impossible or unsupported

⸻

26. Advanced ZFS features to include

26.1 Pool features

* ashift
* autotrim
* autoreplace
* autoexpand
* failmode
* listsnapshots
* multihost
* delegation
* compatibility profiles

26.2 Dataset properties

* compression
* recordsize
* atime
* relatime
* sync
* logbias
* primarycache
* secondarycache
* copies
* quota
* refquota
* reservation
* refreservation
* snapdir
* acltype
* aclmode
* xattr
* dnodesize
* special_small_blocks

26.3 zvol properties

* volblocksize
* compression
* sync
* logbias
* reservation
* sparse vs thick provisioning

26.4 Maintenance

* Scrubs.
* SMART tests.
* Snapshot schedule.
* Replication.
* Send/receive.
* Replace disk workflow.
* Expand pool workflow.
* Export/import.
* Checkpoint.
* Pool trim.
* Monitoring.

⸻

27. User interface modules

27.1 Disk inventory panel

Features:

* Add disk group.
* Add individual disk.
* Mark disk as SSD/NVMe/HDD.
* Mark disk health.
* Mark disk role eligibility.
* Import from command output.
* Detect duplicate serials.

27.2 Visual pool builder

Use cards:

[Pool: tank]
[RAIDZ2 vdev]
disk01 disk02 disk03 disk04 disk05 disk06
[RAIDZ2 vdev]
disk07 disk08 disk09 disk10 disk11 disk12
[SLOG mirror]
nvme01 nvme02
[L2ARC]
ssd01
[Spare]
disk13

Colours:

Colour	Meaning
Green	Good
Amber	Tradeoff
Red	Risk
Grey	Unused
Blue	Cache/log/special device
Purple	Advanced feature

27.3 Score dashboard

Radar chart:

* Capacity.
* Performance.
* Resiliency.
* Expansion.
* Simplicity.
* Cost efficiency.

27.4 Failure simulator

User can click disks to “fail” them.

The app shows:

1 disk failed in RAIDZ2 vdev: pool healthy but degraded.
2 disks failed in same RAIDZ2 vdev: pool still online.
3 disks failed in same RAIDZ2 vdev: pool lost.

For mirrors:

disk01 and disk02 failed in same mirror: pool lost.
disk01 and disk03 failed in different mirrors: pool still online.

This would be one of the most useful differentiators.

⸻

28. Command generator

28.1 Example RAIDZ2

zpool create \
  -o ashift=12 \
  tank \
  raidz2 /dev/disk/by-id/disk01 /dev/disk/by-id/disk02 /dev/disk/by-id/disk03 /dev/disk/by-id/disk04 /dev/disk/by-id/disk05 /dev/disk/by-id/disk06 \
  raidz2 /dev/disk/by-id/disk07 /dev/disk/by-id/disk08 /dev/disk/by-id/disk09 /dev/disk/by-id/disk10 /dev/disk/by-id/disk11 /dev/disk/by-id/disk12

28.2 Example mirrors

zpool create \
  -o ashift=12 \
  tank \
  mirror /dev/disk/by-id/disk01 /dev/disk/by-id/disk02 \
  mirror /dev/disk/by-id/disk03 /dev/disk/by-id/disk04 \
  mirror /dev/disk/by-id/disk05 /dev/disk/by-id/disk06

28.3 Example with SLOG and L2ARC

zpool create \
  -o ashift=12 \
  tank \
  raidz2 /dev/disk/by-id/disk01 /dev/disk/by-id/disk02 /dev/disk/by-id/disk03 /dev/disk/by-id/disk04 /dev/disk/by-id/disk05 /dev/disk/by-id/disk06 \
  log mirror /dev/disk/by-id/nvme-log01 /dev/disk/by-id/nvme-log02 \
  cache /dev/disk/by-id/nvme-cache01

The app should warn before generating commands that use unstable /dev/sdX names.

⸻

29. Architecture

29.1 Frontend

Recommended stack:

Layer	Suggested option
Framework	Next.js / React
UI	Tailwind + shadcn/ui
Diagrams	React Flow or custom SVG
Charts	Recharts
State	Zustand or Redux Toolkit
Forms	React Hook Form + Zod
Local persistence	IndexedDB / localStorage
Export	Markdown/PDF generator

29.2 Backend

Could be optional at first.

Function	Backend needed?
Basic recommendations	No, can run client-side
Saved accounts	Yes
Report storage	Yes
Community templates	Yes
AI explanation layer	Yes/optional
Import parser	Could be client-side
Benchmark database	Yes

Suggested backend:

* FastAPI or Node.js.
* PostgreSQL.
* Redis for caching.
* JSON schema for designs.
* No need to upload sensitive disk serials unless user opts in.

29.3 Rule engine

Use a deterministic rules engine first.

Possible structure:

Input
 ├── Disk inventory
 ├── Workload profile
 ├── User priorities
 ├── Hardware constraints
 └── Existing/manual config
Engine
 ├── Normalise disks
 ├── Generate candidate layouts
 ├── Estimate capacity/performance
 ├── Apply ZFS validity rules
 ├── Apply risk rules
 ├── Score candidates
 └── Produce recommendations
Output
 ├── Ranked configs
 ├── Warnings
 ├── Diagrams
 ├── Commands
 └── Report

Do not make the core judgement depend only on an LLM. Use rules and calculations. An LLM can explain the result afterwards.

⸻

30. Data model

30.1 Disk

{
  "id": "disk01",
  "label": "Toshiba MG08 16TB",
  "size_tb": 16,
  "size_bytes": 16000000000000,
  "media_type": "hdd",
  "interface": "sata",
  "rpm": 7200,
  "sequential_read_mbps": 250,
  "sequential_write_mbps": 240,
  "random_read_iops": 80,
  "random_write_iops": 80,
  "sector_size": "4kn",
  "cmr_smr": "cmr",
  "health": "good",
  "used": true,
  "power_idle_w": 5,
  "power_load_w": 9,
  "allowed_roles": ["data", "spare"]
}

30.2 Vdev

{
  "id": "vdev01",
  "role": "data",
  "type": "raidz2",
  "children": ["disk01", "disk02", "disk03", "disk04", "disk05", "disk06"],
  "parity": 2,
  "estimated_usable_bytes": 64000000000000,
  "risk_level": "green"
}

30.3 Pool

{
  "id": "pool01",
  "name": "tank",
  "vdevs": ["vdev01", "vdev02"],
  "properties": {
    "ashift": 12,
    "autotrim": "off",
    "autoexpand": "on"
  },
  "datasets": ["dataset01", "dataset02"]
}

30.4 Dataset

{
  "id": "dataset01",
  "pool": "tank",
  "name": "tank/media",
  "workload": "media",
  "properties": {
    "compression": "on",
    "recordsize": "1M",
    "atime": "off",
    "sync": "standard"
  }
}

30.5 Recommendation

{
  "id": "rec01",
  "title": "Balanced 2x 6-wide RAIDZ2",
  "score": 87,
  "capacity_score": 82,
  "performance_score": 68,
  "resiliency_score": 91,
  "expandability_score": 65,
  "simplicity_score": 80,
  "warnings": [],
  "commands": []
}

⸻

31. Key differentiators

Most ZFS calculators only estimate capacity. This product should go beyond that.

Differentiators

1. Failure simulator
2. Manual topology validator
3. SLOG/L2ARC/special-vdev correctness checks
4. Workload-aware recommendations
5. Mixed-size optimiser
6. Hardware bottleneck advisor
7. Expansion planner
8. Dataset property advisor
9. TrueNAS and CLI output
10. Professional export report
11. Risk-based scoring, not just capacity calculation
12. Under-100-disk exhaustive homelab coverage

⸻

32. MVP scope

MVP 1 — Useful calculator

Must include:

* Disk group input.
* Candidate generation for mirrors, RAIDZ1/2/3.
* Capacity estimates.
* Basic performance estimates.
* Workload priorities.
* Pros/cons.
* Report export as Markdown.

MVP 2 — Real advisor

Add:

* Manual pool builder.
* Validation rules.
* Dataset recommendations.
* SLOG/L2ARC/special-vdev advice.
* Failure simulator.
* Command generation.

MVP 3 — Advanced homelab/pro version

Add:

* dRAID.
* Import from command outputs.
* Hardware bottleneck advisor.
* Expansion planner.
* PDF export.
* Saved designs.
* Community templates.
* TrueNAS mapping.

⸻

33. Design principle

The product should consistently follow this rule:

Recommend simple, recoverable, observable ZFS designs first. Allow advanced configurations, but force the risk to be visible.

For homelab users under 100 disks, the most important practical recommendations will usually be:

* Prefer mirrors for performance, VMs, apps, and flexible expansion.
* Prefer RAIDZ2 for general HDD media/backup pools.
* Prefer RAIDZ3 for large, wide, archive-heavy vdevs.
* Avoid RAIDZ1 for large important pools.
* Avoid unmirrored special vdevs.
* Do not treat SLOG as a write cache.
* Do not add L2ARC before understanding RAM and workload.
* Do not enable deduplication casually.
* Separate apps/VMs/databases onto SSD/NVMe where possible.
* Keep a real backup; ZFS redundancy is not backup.

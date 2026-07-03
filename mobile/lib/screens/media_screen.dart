import 'package:flutter/material.dart';
import '../services/jarvis_connection.dart';

class MediaScreen extends StatelessWidget {
  final JarvisConnection connection;
  const MediaScreen({super.key, required this.connection});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: connection,
      builder: (_, __) {
        final plex      = connection.mediaData['plex'] as Map? ?? {};
        final downloads = (connection.mediaData['downloads'] as List?) ?? [];
        final sessions  = (plex['sessions'] as List?) ?? [];
        final history   = (plex['history']  as List?) ?? [];
        final recent    = (plex['recent']   as List?) ?? [];
        final counts    = plex['library_counts'] as Map? ?? {};

        return RefreshIndicator(
          onRefresh: connection.fetchMedia,
          color: const Color(0xFF00B4FF),
          backgroundColor: const Color(0xFF0D1520),
          child: CustomScrollView(
            slivers: [
              // Library counts strip
              SliverToBoxAdapter(
                child: _CountsStrip(
                  movies: counts['movie']?.toString() ?? '—',
                  shows:  counts['show']?.toString()  ?? '—',
                ),
              ),

              // Now playing
              if (sessions.isNotEmpty) ...[
                _SliverHeader('NOW PLAYING'),
                SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (_, i) => _NowPlayingCard(session: sessions[i] as Map),
                    childCount: sessions.length,
                  ),
                ),
              ],

              // Downloads
              if (downloads.isNotEmpty) ...[
                _SliverHeader('DOWNLOADS'),
                SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (_, i) => _DownloadCard(item: downloads[i] as Map),
                    childCount: downloads.length,
                  ),
                ),
              ],

              // Recently watched
              if (history.isNotEmpty) ...[
                _SliverHeader('RECENTLY WATCHED'),
                SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (_, i) => _HistoryCard(item: history[i] as Map),
                    childCount: history.length,
                  ),
                ),
              ],

              // Recently added
              if (recent.isNotEmpty) ...[
                _SliverHeader('RECENTLY ADDED'),
                SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (_, i) => _RecentCard(item: recent[i] as Map),
                    childCount: recent.length,
                  ),
                ),
              ],

              if (sessions.isEmpty && downloads.isEmpty && history.isEmpty)
                SliverFillRemaining(
                  child: Center(
                    child: connection.mediaLoading
                        ? const CircularProgressIndicator(
                            color: Color(0xFF00B4FF))
                        : _EmptyState(
                            icon: Icons.movie_outlined,
                            label: connection.isConnected
                                ? 'No media activity'
                                : 'Disconnected',
                          ),
                  ),
                ),

              const SliverToBoxAdapter(child: SizedBox(height: 20)),
            ],
          ),
        );
      },
    );
  }
}

// ── Counts strip ──────────────────────────────────────────────────────────────
class _CountsStrip extends StatelessWidget {
  final String movies;
  final String shows;
  const _CountsStrip({required this.movies, required this.shows});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      padding: const EdgeInsets.symmetric(vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1520),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1A2535)),
      ),
      child: Row(
        children: [
          _Stat(label: 'MOVIES', value: movies, icon: Icons.movie_outlined),
          _vDivider(),
          _Stat(label: 'TV SHOWS', value: shows, icon: Icons.tv_outlined),
        ],
      ),
    );
  }

  Widget _vDivider() => Container(
    width: 1, height: 36, color: const Color(0xFF1A2535));
}

class _Stat extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  const _Stat({required this.label, required this.value, required this.icon});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Icon(icon, color: const Color(0xFF00B4FF), size: 18),
          const SizedBox(height: 4),
          Text(value,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.bold,
                fontFamily: 'monospace',
              )),
          Text(label,
              style: const TextStyle(
                color: Colors.white38,
                fontSize: 9,
                letterSpacing: 2,
              )),
        ],
      ),
    );
  }
}

// ── Section header ────────────────────────────────────────────────────────────
class _SliverHeader extends StatelessWidget {
  final String title;
  const _SliverHeader(this.title);

  @override
  Widget build(BuildContext context) {
    return SliverToBoxAdapter(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
        child: Text(
          title,
          style: const TextStyle(
            color: Color(0xFF00B4FF),
            fontSize: 10,
            letterSpacing: 3,
            fontFamily: 'monospace',
          ),
        ),
      ),
    );
  }
}

// ── Now playing card ──────────────────────────────────────────────────────────
class _NowPlayingCard extends StatelessWidget {
  final Map session;
  const _NowPlayingCard({required this.session});

  @override
  Widget build(BuildContext context) {
    final progress = (session['progress'] as num? ?? 0).toInt();
    final elapsed  = session['elapsed_min'] as num? ?? 0;
    final duration = session['duration_min'] as num? ?? 0;

    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFF00FF88).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                      color: const Color(0xFF00FF88).withOpacity(0.4)),
                ),
                child: const Text('● PLAYING',
                    style: TextStyle(
                      color: Color(0xFF00FF88),
                      fontSize: 9,
                      letterSpacing: 1,
                    )),
              ),
              const Spacer(),
              Text(
                '${elapsed.toInt()}m / ${duration.toInt()}m',
                style: const TextStyle(color: Colors.white38, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            session['title'] as String? ?? 'Unknown',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(Icons.person_outline,
                  size: 12, color: Colors.white38),
              const SizedBox(width: 4),
              Text(
                session['user'] as String? ?? '',
                style: const TextStyle(color: Colors.white38, fontSize: 11),
              ),
              const SizedBox(width: 12),
              Icon(Icons.devices_outlined,
                  size: 12, color: Colors.white38),
              const SizedBox(width: 4),
              Text(
                session['player'] as String? ?? '',
                style: const TextStyle(color: Colors.white38, fontSize: 11),
              ),
            ],
          ),
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: progress / 100,
              backgroundColor: Colors.white12,
              color: const Color(0xFF00B4FF),
              minHeight: 3,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Download card ─────────────────────────────────────────────────────────────
class _DownloadCard extends StatelessWidget {
  final Map item;
  const _DownloadCard({required this.item});

  Color get _stateColor {
    final s = item['state'] as String? ?? '';
    if (s.contains('download')) return const Color(0xFF00B4FF);
    if (s == 'stalledDL') return const Color(0xFFFFAA00);
    if (s == 'pausedDL')  return Colors.white38;
    return Colors.white54;
  }

  @override
  Widget build(BuildContext context) {
    final progress = (item['progress'] as num? ?? 0).toInt();

    return _Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  item['name'] as String? ?? '',
                  style: const TextStyle(color: Colors.white, fontSize: 12),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                item['dlspeed'] as String? ?? '',
                style: TextStyle(
                  color: _stateColor,
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: LinearProgressIndicator(
                    value: progress / 100,
                    backgroundColor: Colors.white12,
                    color: _stateColor,
                    minHeight: 3,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Text(
                '$progress%',
                style: const TextStyle(
                  color: Colors.white38,
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
              ),
              const SizedBox(width: 8),
              Text(
                item['size'] as String? ?? '',
                style: const TextStyle(color: Colors.white24, fontSize: 10),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── History card ──────────────────────────────────────────────────────────────
class _HistoryCard extends StatelessWidget {
  final Map item;
  const _HistoryCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return _Card(
      child: Row(
        children: [
          Icon(
            item['type'] == 'movie'
                ? Icons.movie_outlined
                : Icons.tv_outlined,
            color: const Color(0xFF00B4FF),
            size: 18,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  item['title'] as String? ?? '',
                  style: const TextStyle(color: Colors.white, fontSize: 12),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 3),
                Row(
                  children: [
                    Text(
                      item['user'] as String? ?? '',
                      style: const TextStyle(
                          color: Colors.white38, fontSize: 10),
                    ),
                    if ((item['player'] as String? ?? '').isNotEmpty) ...[
                      const Text('  ·  ',
                          style: TextStyle(
                              color: Colors.white24, fontSize: 10)),
                      Text(
                        item['player'] as String? ?? '',
                        style: const TextStyle(
                            color: Colors.white24, fontSize: 10),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          Text(
            item['time'] as String? ?? '',
            style: const TextStyle(
              color: Colors.white24,
              fontSize: 10,
              fontFamily: 'monospace',
            ),
          ),
        ],
      ),
    );
  }
}

// ── Recently added card ───────────────────────────────────────────────────────
class _RecentCard extends StatelessWidget {
  final Map item;
  const _RecentCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return _Card(
      child: Row(
        children: [
          Icon(
            item['type'] == 'movie'
                ? Icons.movie_outlined
                : Icons.tv_outlined,
            color: Colors.white38,
            size: 16,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              item['title'] as String? ?? '',
              style: const TextStyle(color: Colors.white70, fontSize: 12),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if ((item['year'] as String? ?? '').isNotEmpty)
            Text(
              item['year'].toString(),
              style: const TextStyle(color: Colors.white24, fontSize: 11),
            ),
        ],
      ),
    );
  }
}

// ── Shared card container ─────────────────────────────────────────────────────
class _Card extends StatelessWidget {
  final Widget child;
  const _Card({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1520),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1A2535)),
      ),
      child: child,
    );
  }
}

class _EmptyState extends StatelessWidget {
  final IconData icon;
  final String label;
  const _EmptyState({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(icon, color: Colors.white12, size: 48),
        const SizedBox(height: 12),
        Text(label,
            style: const TextStyle(
              color: Colors.white24,
              fontSize: 12,
              fontFamily: 'monospace',
              letterSpacing: 2,
            )),
      ],
    );
  }
}

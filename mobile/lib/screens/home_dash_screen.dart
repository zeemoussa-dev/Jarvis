import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import '../services/jarvis_connection.dart';

class HomeDashScreen extends StatelessWidget {
  final JarvisConnection connection;
  const HomeDashScreen({super.key, required this.connection});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: connection,
      builder: (_, __) {
        final people  = (connection.homeData['presence'] as List?) ?? [];
        final lights  = (connection.homeData['lights']   as List?) ?? [];
        final weather = connection.envData['weather']    as Map?   ?? {};
        final dyson   = connection.envData['dyson']      as Map?   ?? {};
        final nas     = connection.envData['nas']        as Map?   ?? {};

        return RefreshIndicator(
          onRefresh: connection.fetchHome,
          color: const Color(0xFF00B4FF),
          backgroundColor: const Color(0xFF0D1520),
          child: CustomScrollView(
            slivers: [
              // People presence
              if (people.isNotEmpty) ...[
                _SliverHeader('PRESENCE'),
                SliverToBoxAdapter(
                  child: _PeopleRow(people: people),
                ),
              ],

              // Weather
              if (weather.isNotEmpty) ...[
                _SliverHeader('WEATHER  ·  ${weather['location'] ?? 'Dubai'}'),
                SliverToBoxAdapter(child: _WeatherCard(weather: weather)),
              ],

              // Air quality (Dyson)
              if (dyson.isNotEmpty) ...[
                _SliverHeader('AIR QUALITY  ·  INDOOR'),
                SliverToBoxAdapter(child: _DysonCard(dyson: dyson)),
              ],

              // NAS
              if (nas.isNotEmpty) ...[
                _SliverHeader('NAS  ·  ${nas['model'] ?? 'Synology'}'),
                SliverToBoxAdapter(child: _NasCard(nas: nas)),
              ],

              // Lights
              if (lights.isNotEmpty) ...[
                _SliverHeader('LIGHTS'),
                SliverPadding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  sliver: SliverGrid(
                    delegate: SliverChildBuilderDelegate(
                      (_, i) => _LightCard(
                        light: lights[i] as Map,
                        connection: connection,
                      ),
                      childCount: lights.length,
                    ),
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2,
                      mainAxisSpacing: 8,
                      crossAxisSpacing: 8,
                      childAspectRatio: 2.4,
                    ),
                  ),
                ),
              ],

              if (people.isEmpty && weather.isEmpty && lights.isEmpty)
                SliverFillRemaining(
                  child: Center(
                    child: connection.homeLoading
                        ? const CircularProgressIndicator(
                            color: Color(0xFF00B4FF))
                        : _EmptyState(
                            icon: Icons.home_outlined,
                            label: connection.isConnected
                                ? 'No home data'
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

// ── People row ────────────────────────────────────────────────────────────────
class _PeopleRow extends StatelessWidget {
  final List people;
  const _PeopleRow({required this.people});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: people
            .map((p) => Expanded(child: _PersonCard(person: p as Map)))
            .toList(),
      ),
    );
  }
}

class _PersonCard extends StatelessWidget {
  final Map person;
  const _PersonCard({required this.person});

  bool get _isHome =>
      (person['state'] as String? ?? '').toLowerCase() == 'home';

  @override
  Widget build(BuildContext context) {
    final color =
        _isHome ? const Color(0xFF00FF88) : Colors.white24;

    return Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1520),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Column(
        children: [
          CircleAvatar(
            radius: 22,
            backgroundColor: color.withOpacity(0.15),
            child: Text(
              (person['name'] as String? ?? '?')[0].toUpperCase(),
              style: TextStyle(
                color: color,
                fontSize: 18,
                fontWeight: FontWeight.bold,
                fontFamily: 'monospace',
              ),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            person['name'] as String? ?? '',
            style: const TextStyle(
              color: Colors.white,
              fontSize: 13,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 2),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: color,
                  boxShadow: _isHome
                      ? [BoxShadow(
                          color: color.withOpacity(0.6), blurRadius: 4)]
                      : null,
                ),
              ),
              const SizedBox(width: 5),
              Text(
                _isHome ? 'HOME' : 'AWAY',
                style: TextStyle(
                  color: color,
                  fontSize: 10,
                  letterSpacing: 2,
                  fontFamily: 'monospace',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

// ── Weather card ──────────────────────────────────────────────────────────────
class _WeatherCard extends StatelessWidget {
  final Map weather;
  const _WeatherCard({required this.weather});

  String _weatherIcon(int? code) {
    if (code == null) return '🌡';
    if (code == 0) return '☀️';
    if (code <= 2) return '⛅';
    if (code <= 48) return '☁️';
    if (code <= 67) return '🌧';
    if (code <= 77) return '❄️';
    if (code <= 99) return '⛈';
    return '🌡';
  }

  @override
  Widget build(BuildContext context) {
    final temp     = weather['temp']     as num?;
    final feels    = weather['feels_like'] as num?;
    final humidity = weather['humidity'] as num?;
    final wind     = weather['wind_kmh'] as num?;
    final uv       = weather['uv']       as num?;
    final code     = weather['code']     as int?;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1520),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1A2535)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Text(
                _weatherIcon(code),
                style: const TextStyle(fontSize: 40),
              ),
              const SizedBox(width: 16),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    temp != null ? '${temp.round()}°C' : '—',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 36,
                      fontWeight: FontWeight.w300,
                      fontFamily: 'monospace',
                    ),
                  ),
                  Text(
                    feels != null ? 'Feels like ${feels.round()}°C' : '',
                    style: const TextStyle(
                      color: Colors.white38,
                      fontSize: 12,
                    ),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              _WeatherStat('💧', '${humidity?.round() ?? '—'}%', 'Humidity'),
              _WeatherStat('💨', '${wind?.round() ?? '—'} km/h', 'Wind'),
              _WeatherStat('☀️', 'UV ${uv?.round() ?? '—'}', 'UV Index'),
            ],
          ),
        ],
      ),
    );
  }
}

class _WeatherStat extends StatelessWidget {
  final String emoji;
  final String value;
  final String label;
  const _WeatherStat(this.emoji, this.value, this.label);

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(emoji, style: const TextStyle(fontSize: 16)),
          const SizedBox(height: 4),
          Text(value,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontFamily: 'monospace',
              )),
          Text(label,
              style: const TextStyle(color: Colors.white38, fontSize: 9)),
        ],
      ),
    );
  }
}

// ── Dyson / Air quality card ──────────────────────────────────────────────────
class _DysonCard extends StatelessWidget {
  final Map dyson;
  const _DysonCard({required this.dyson});

  Color _aqiColor(num? aqi) {
    if (aqi == null) return Colors.white38;
    if (aqi <= 50)  return const Color(0xFF00FF88);
    if (aqi <= 100) return const Color(0xFFFFAA00);
    return const Color(0xFFFF4444);
  }

  @override
  Widget build(BuildContext context) {
    final aqi      = dyson['aqi']      as num?;
    final pm25     = dyson['pm25']     as num?;
    final pm10     = dyson['pm10']     as num?;
    final voc      = dyson['voc']      as num?;
    final humidity = dyson['humidity'] as num?;
    final temp     = dyson['temp']     as num?;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1520),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1A2535)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 60,
                height: 60,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: _aqiColor(aqi).withOpacity(0.5),
                    width: 2,
                  ),
                ),
                child: Center(
                  child: Text(
                    aqi?.round().toString() ?? '—',
                    style: TextStyle(
                      color: _aqiColor(aqi),
                      fontSize: 20,
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Air Quality Index',
                      style: TextStyle(color: _aqiColor(aqi), fontSize: 13),
                    ),
                    if (temp != null)
                      Text(
                        'Indoor ${temp.round()}°C  ·  ${humidity?.round() ?? '—'}% RH',
                        style: const TextStyle(
                          color: Colors.white38,
                          fontSize: 11,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              _AqiStat('PM2.5', pm25?.round().toString() ?? '—', 'μg/m³'),
              _AqiStat('PM10',  pm10?.round().toString() ?? '—', 'μg/m³'),
              _AqiStat('VOC',   voc?.round().toString()  ?? '—', 'ppb'),
            ],
          ),
        ],
      ),
    );
  }
}

class _AqiStat extends StatelessWidget {
  final String label;
  final String value;
  final String unit;
  const _AqiStat(this.label, this.value, this.unit);

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(value,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontFamily: 'monospace',
              )),
          Text('$label $unit',
              style: const TextStyle(
                color: Colors.white38,
                fontSize: 9,
                letterSpacing: 1,
              )),
        ],
      ),
    );
  }
}

// ── NAS card ──────────────────────────────────────────────────────────────────
class _NasCard extends StatelessWidget {
  final Map nas;
  const _NasCard({required this.nas});

  @override
  Widget build(BuildContext context) {
    final volumes = (nas['volumes'] as List?) ?? [];
    final cpu     = nas['cpu_pct'] as num? ?? 0;
    final ram     = nas['ram_pct'] as num? ?? 0;
    final temp    = nas['temp'];

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1520),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF1A2535)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              _NasStat('CPU', '${cpu.round()}%'),
              _NasStat('RAM', '${ram.round()}%'),
              if (temp != null) _NasStat('TEMP', '$temp°C'),
            ],
          ),
          if (volumes.isNotEmpty) ...[
            const SizedBox(height: 12),
            const Divider(color: Color(0xFF1A2535), height: 1),
            const SizedBox(height: 12),
            ...volumes.map((v) => _VolumeBar(volume: v as Map)),
          ],
        ],
      ),
    );
  }
}

class _NasStat extends StatelessWidget {
  final String label;
  final String value;
  const _NasStat(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(
        children: [
          Text(value,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
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

class _VolumeBar extends StatelessWidget {
  final Map volume;
  const _VolumeBar({required this.volume});

  @override
  Widget build(BuildContext context) {
    final pct  = (volume['used_pct'] as num? ?? 0).toInt();
    final used = volume['used_gb']  as num? ?? 0;
    final total = volume['total_gb'] as num? ?? 0;
    final color = pct > 85
        ? const Color(0xFFFF4444)
        : pct > 70
            ? const Color(0xFFFFAA00)
            : const Color(0xFF00B4FF);

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        children: [
          Row(
            children: [
              Text(
                volume['name'] as String? ?? 'Volume',
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
              const Spacer(),
              Text(
                '${used.round()} / ${total.round()} GB',
                style: const TextStyle(
                  color: Colors.white38,
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
              ),
              const SizedBox(width: 8),
              Text(
                '$pct%',
                style: TextStyle(
                  color: color,
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              value: pct / 100,
              backgroundColor: Colors.white12,
              color: color,
              minHeight: 4,
            ),
          ),
        ],
      ),
    );
  }
}

// ── Light card ────────────────────────────────────────────────────────────────
class _LightCard extends StatelessWidget {
  final Map light;
  final JarvisConnection connection;
  const _LightCard({required this.light, required this.connection});

  @override
  Widget build(BuildContext context) {
    final isOn = light['state'] == 'on';
    final color = isOn ? const Color(0xFFFFCC44) : Colors.white24;

    return GestureDetector(
      onTap: () => _toggle(),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: isOn
              ? const Color(0xFFFFCC44).withOpacity(0.08)
              : const Color(0xFF0D1520),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: isOn
                ? const Color(0xFFFFCC44).withOpacity(0.35)
                : const Color(0xFF1A2535),
          ),
        ),
        child: Row(
          children: [
            Icon(
              isOn ? Icons.lightbulb : Icons.lightbulb_outline,
              color: color,
              size: 18,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                light['name'] as String? ?? '',
                style: TextStyle(
                  color: isOn ? Colors.white : Colors.white38,
                  fontSize: 11,
                  fontFamily: 'monospace',
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _toggle() async {
    final host  = connection.activeHost;
    final token = connection.wsToken;
    if (host.isEmpty) return;

    final url = token.isEmpty
        ? 'http://$host/api/home/toggle'
        : 'http://$host/api/home/toggle?token=$token';

    try {
      await http.post(
        Uri.parse(url),
        headers: {'Content-Type': 'application/json'},
        body: '{"entity_id":"${light['entity_id']}","action":"toggle"}',
      );
      connection.fetchHome();
    } catch (e) {
      debugPrint('[Light] Toggle failed: $e');
    }
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
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

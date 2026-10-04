import 'dart:async';

import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';

void main() => runApp(StudioApp(api: StudioApi()));
const ink = Color(0xff172a3a);
const teal = Color(0xff087f8c);
const bg = Color(0xfff3f6f7);
const statusNames = {
  'INVITED': 'Ожидает клиента',
  'CONSENT': 'Согласие на AI',
  'CHATTING': 'Клиент отвечает',
  'APPROVAL': 'Подтверждение отзыва',
  'PUBLIC': 'Разрешение публикации',
  'DONE': 'Отзыв получен',
  'STOPPED': 'Отказ клиента',
  'GENERATING': 'AI готовит пост',
  'DRAFT': 'Пост готов к проверке',
  'QUEUED': 'В очереди',
  'CREATING': 'Создание контейнера',
  'WAITING': 'Instagram обрабатывает фото',
  'PUBLISHING': 'Публикуется',
  'PUBLISHED': 'Опубликован',
  'DEMO': 'Тест завершён',
  'FAILED': 'Ошибка',
  'UNCERTAIN': 'Нужна сверка с Instagram',
  'CANCELLED': 'Публикация отменена',
};
String stageOf(Map job) =>
    statusNames[job['post']?['status'] ?? job['review']?['stage']] ??
    'Новая работа';

class StudioApp extends StatelessWidget {
  final StudioApi api;
  const StudioApp({super.key, required this.api});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Review Studio',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: teal),
      scaffoldBackgroundColor: bg,
      useMaterial3: true,
      textTheme: ThemeData.light().textTheme.apply(
        bodyColor: ink,
        displayColor: ink,
      ),
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        filled: true,
        fillColor: Colors.white,
      ),
      cardTheme: const CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: EdgeInsets.zero,
      ),
    ),
    home: Home(api: api),
  );
}

class Home extends StatefulWidget {
  final StudioApi api;
  const Home({super.key, required this.api});
  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  bool signedIn = false, loading = true, busy = false;
  String? error;
  List<Map<String, dynamic>> jobs = [];
  Map config = {};
  Map<String, dynamic>? selected;
  String search = '';
  final username = TextEditingController(text: 'owner');
  final password = TextEditingController();
  Timer? timer;
  @override
  void initState() {
    super.initState();
    boot();
  }

  Future<void> boot() async {
    try {
      signedIn = await widget.api.restore();
      if (signedIn) await load();
    } catch (e) {
      error = errorText(e);
      signedIn = false;
    }
    if (mounted) setState(() => loading = false);
    timer = Timer.periodic(const Duration(seconds: 8), (_) {
      if (signedIn && !busy) load(silent: true);
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    username.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> load({bool silent = false}) async {
    try {
      final result = await Future.wait([
        widget.api.request('/jobs/'),
        widget.api.request('/config/'),
      ]);
      if (!mounted) return;
      final list = (result[0] as List)
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
      setState(() {
        jobs = list;
        config = result[1];
        if (selected != null) {
          selected = list.where((e) => e['id'] == selected!['id']).firstOrNull;
        }
        if (!silent) error = null;
      });
    } catch (e) {
      if (mounted && !silent) setState(() => error = errorText(e));
    }
  }

  Future<void> login() async {
    if (username.text.trim().isEmpty || password.text.isEmpty) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.api.login(username.text.trim(), password.text);
      await load();
      if (mounted) setState(() => signedIn = true);
      password.clear();
    } catch (e) {
      if (mounted) setState(() => error = errorText(e));
    }
    if (mounted) setState(() => busy = false);
  }

  Future<void> create() async {
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (_) => CreateJob(api: widget.api),
    );
    if (result != null) {
      selected = result;
      await load();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!signedIn) {
      return Scaffold(
        body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: SizedBox(
              width: 410,
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.auto_awesome_outlined,
                        size: 42,
                        color: teal,
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        'Review Studio',
                        style: TextStyle(
                          fontSize: 30,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text('Работа → отзыв клиента → пост в Instagram'),
                      const SizedBox(height: 28),
                      TextField(
                        controller: username,
                        decoration: const InputDecoration(labelText: 'Логин'),
                      ),
                      const SizedBox(height: 16),
                      TextField(
                        controller: password,
                        obscureText: true,
                        onSubmitted: (_) => busy ? null : login(),
                        decoration: const InputDecoration(labelText: 'Пароль'),
                      ),
                      if (error != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 16),
                          child: Text(
                            error!,
                            style: const TextStyle(color: Colors.red),
                          ),
                        ),
                      const SizedBox(height: 24),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                          onPressed: busy ? null : login,
                          child: Text(busy ? 'Вход…' : 'Войти'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      );
    }
    final filtered = jobs
        .where(
          (j) => '${j['title']} ${j['city']}'.toLowerCase().contains(
            search.toLowerCase(),
          ),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: const Text(
          'Review Studio',
          style: TextStyle(fontWeight: FontWeight.w700),
        ),
        actions: [
          IconButton(
            tooltip: 'Обновить',
            onPressed: load,
            icon: const Icon(Icons.refresh),
          ),
          IconButton(
            tooltip: 'Выйти',
            onPressed: () async {
              await widget.api.logout();
              if (mounted) {
                setState(() {
                  signedIn = false;
                  selected = null;
                  jobs = [];
                });
              }
            },
            icon: const Icon(Icons.logout),
          ),
          const SizedBox(width: 12),
        ],
      ),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            color: config['demo_mode'] == true
                ? const Color(0xffe4f2ef)
                : const Color(0xfffff1d6),
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            child: Text(
              config['demo_mode'] == true
                  ? 'Деморежим · AI и Instagram имитируются. Ничего не публикуется.'
                  : 'Рабочий режим · ${config['instagram_enabled'] == true ? 'Публикация в Instagram включена' : 'Публикация в Instagram отключена'}',
            ),
          ),
          if (error != null)
            MaterialBanner(
              content: Text(error!),
              actions: [
                TextButton(
                  onPressed: () => setState(() => error = null),
                  child: const Text('Закрыть'),
                ),
              ],
            ),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final wide = constraints.maxWidth >= 1000;
                final list = Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Expanded(
                            child: Text(
                              'Выполненные работы',
                              style: TextStyle(
                                fontSize: 24,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          FilledButton.icon(
                            onPressed: create,
                            icon: const Icon(Icons.add),
                            label: const Text('Добавить'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        '${jobs.length} работ · ${jobs.where((j) => j['review']?['stage'] == 'DONE').length} отзывов · ${jobs.where((j) => ['PUBLISHED', 'DEMO'].contains(j['post']?['status'])).length} готовых публикаций',
                      ),
                      const SizedBox(height: 20),
                      TextField(
                        onChanged: (v) => setState(() => search = v),
                        decoration: const InputDecoration(
                          hintText: 'Найти работу',
                          prefixIcon: Icon(Icons.search),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Expanded(
                        child: filtered.isEmpty
                            ? const Center(
                                child: Text(
                                  'Добавьте работу с фотографией,\nзатем пригласите клиента оставить отзыв.',
                                  textAlign: TextAlign.center,
                                ),
                              )
                            : ListView.separated(
                                itemCount: filtered.length,
                                separatorBuilder: (_, i) =>
                                    const SizedBox(height: 12),
                                itemBuilder: (_, i) {
                                  final j = filtered[i];
                                  return Card(
                                    child: ListTile(
                                      contentPadding: const EdgeInsets.all(16),
                                      selected: j['id'] == selected?['id'],
                                      leading: const Icon(
                                        Icons.handyman_outlined,
                                        color: teal,
                                      ),
                                      title: Text(
                                        j['title'],
                                        style: const TextStyle(
                                          fontWeight: FontWeight.w600,
                                        ),
                                      ),
                                      subtitle: Padding(
                                        padding: const EdgeInsets.only(top: 8),
                                        child: Text(
                                          '${j['city']} · ${stageOf(j)}',
                                        ),
                                      ),
                                      trailing: const Icon(Icons.chevron_right),
                                      onTap: () {
                                        if (wide) {
                                          setState(() => selected = j);
                                        } else {
                                          Navigator.of(context)
                                              .push(
                                                MaterialPageRoute(
                                                  builder: (_) => MobileDetail(
                                                    api: widget.api,
                                                    jobId: j['id'],
                                                    config: config,
                                                  ),
                                                ),
                                              )
                                              .then((_) => load());
                                        }
                                      },
                                    ),
                                  );
                                },
                              ),
                      ),
                    ],
                  ),
                );
                if (!wide) return list;
                return Row(
                  children: [
                    Expanded(flex: 4, child: list),
                    const VerticalDivider(width: 1),
                    Expanded(
                      flex: 5,
                      child: selected == null
                          ? const Center(
                              child: Text(
                                'Выберите работу, чтобы открыть\nотзыв и подготовленный пост.',
                                textAlign: TextAlign.center,
                              ),
                            )
                          : JobDetail(
                              key: ValueKey(selected!['id']),
                              api: widget.api,
                              job: selected!,
                              config: config,
                              reload: load,
                            ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class CreateJob extends StatefulWidget {
  final StudioApi api;
  const CreateJob({super.key, required this.api});
  @override
  State<CreateJob> createState() => _CreateJobState();
}

class _CreateJobState extends State<CreateJob> {
  final form = GlobalKey<FormState>();
  final title = TextEditingController();
  final description = TextEditingController();
  final city = TextEditingController(text: 'Алматы');
  XFile? photo;
  Uint8List? preview;
  bool rights = false, automatic = false, busy = false;
  String? error;
  @override
  void dispose() {
    title.dispose();
    description.dispose();
    city.dispose();
    super.dispose();
  }

  Future<void> choose() async {
    try {
      final file = await openFile(
        acceptedTypeGroups: [
          const XTypeGroup(
            label: 'Фотографии',
            extensions: ['jpg', 'jpeg', 'png', 'webp'],
          ),
        ],
      );
      if (file == null) return;
      if (await file.length() > 8 * 1024 * 1024) {
        if (mounted) setState(() => error = 'Фото должно быть не больше 8 МБ.');
        return;
      }
      final bytes = await file.readAsBytes();
      if (mounted) {
        setState(() {
          photo = file;
          preview = bytes;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = 'Не удалось открыть фото.');
    }
  }

  Future<void> save() async {
    if (!form.currentState!.validate()) return;
    if (photo == null || !rights) {
      setState(
        () => error = 'Добавьте фото и подтвердите право использовать его.',
      );
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final data = FormData.fromMap({
        'title': title.text.trim(),
        'description': description.text.trim(),
        'city': city.text.trim(),
        'photo_rights': rights,
        'auto_publish': automatic,
        'photo': MultipartFile.fromBytes(preview!, filename: photo!.name),
      });
      final result = await widget.api.request(
        '/jobs/',
        method: 'POST',
        data: data,
      );
      if (mounted) Navigator.pop(context, Map<String, dynamic>.from(result));
    } catch (e) {
      if (mounted) {
        setState(() {
          busy = false;
          error = errorText(e);
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Новая выполненная работа'),
    content: SizedBox(
      width: 530,
      child: SingleChildScrollView(
        child: Form(
          key: form,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: title,
                maxLength: 160,
                decoration: const InputDecoration(labelText: 'Название работы'),
                validator: requiredValue,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: description,
                maxLines: 3,
                maxLength: 2000,
                decoration: const InputDecoration(
                  labelText: 'Что сделали — только факты',
                ),
                validator: requiredValue,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: city,
                maxLength: 80,
                decoration: const InputDecoration(labelText: 'Город'),
                validator: requiredValue,
              ),
              OutlinedButton.icon(
                onPressed: busy ? null : choose,
                icon: const Icon(Icons.add_photo_alternate_outlined),
                label: Text(photo?.name ?? 'Загрузить фотографию'),
              ),
              if (preview != null)
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Image.memory(
                    preview!,
                    height: 150,
                    errorBuilder: (_, e, stack) =>
                        const Text('Не удалось показать фото'),
                  ),
                ),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: rights,
                onChanged: busy ? null : (v) => setState(() => rights = v!),
                title: const Text(
                  'Разрешаю обработку фото AI и публикацию. У меня есть права и необходимые согласия на снимок.',
                ),
              ),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: automatic,
                onChanged: busy ? null : (v) => setState(() => automatic = v!),
                title: const Text(
                  'Публиковать автоматически после согласия клиента',
                ),
                subtitle: const Text(
                  'Если выключено, сначала проверите черновик. В деморежиме публикация имитируется.',
                ),
              ),
              if (error != null)
                Text(error!, style: const TextStyle(color: Colors.red)),
            ],
          ),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: busy ? null : () => Navigator.pop(context),
        child: const Text('Отмена'),
      ),
      FilledButton(
        onPressed: busy ? null : save,
        child: Text(busy ? 'Сохранение…' : 'Создать'),
      ),
    ],
  );
}

String? requiredValue(String? value) =>
    value == null || value.trim().isEmpty ? 'Заполните поле' : null;

class MobileDetail extends StatefulWidget {
  final StudioApi api;
  final String jobId;
  final Map config;
  const MobileDetail({
    super.key,
    required this.api,
    required this.jobId,
    required this.config,
  });
  @override
  State<MobileDetail> createState() => _MobileDetailState();
}

class _MobileDetailState extends State<MobileDetail> {
  Map<String, dynamic>? job;
  Timer? timer;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
    timer = Timer.periodic(const Duration(seconds: 8), (_) => load());
  }

  Future<void> load() async {
    try {
      final result = await widget.api.request('/jobs/${widget.jobId}/');
      if (mounted) {
        setState(() {
          job = Map<String, dynamic>.from(result);
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = errorText(e));
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Карточка работы')),
    body: job == null
        ? Center(
            child: error == null
                ? const CircularProgressIndicator()
                : Text(error!),
          )
        : JobDetail(
            api: widget.api,
            job: job!,
            config: widget.config,
            reload: load,
          ),
  );
}

class JobDetail extends StatefulWidget {
  final StudioApi api;
  final Map<String, dynamic> job;
  final Map config;
  final Future<void> Function() reload;
  const JobDetail({
    super.key,
    required this.api,
    required this.job,
    required this.config,
    required this.reload,
  });
  @override
  State<JobDetail> createState() => _JobDetailState();
}

class _JobDetailState extends State<JobDetail> {
  bool busy = false;
  String? error, link;
  Uint8List? photo;
  Map? chat;
  final answer = TextEditingController();
  @override
  void initState() {
    super.initState();
    loadPhoto();
  }

  Future<void> loadPhoto() async {
    if (widget.job['photo_present'] != true) return;
    try {
      final bytes = await widget.api.request(
        '/jobs/${widget.job['id']}/photo/',
        responseType: ResponseType.bytes,
      );
      if (mounted) {
        setState(() => photo = Uint8List.fromList(List<int>.from(bytes)));
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    answer.dispose();
    super.dispose();
  }

  Future<void> action(String name, [Map<String, dynamic>? data]) async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final result = await widget.api.request(
        '/jobs/${widget.job['id']}/$name/',
        method: 'POST',
        data: data ?? {},
      );
      if (mounted) {
        setState(() {
          if (name == 'invite') link = result['telegram_link'];
          if (name == 'demo-chat') {
            chat = result;
            answer.clear();
          }
        });
      }
      await widget.reload();
    } catch (e) {
      if (mounted) setState(() => error = errorText(e));
    }
    if (mounted) setState(() => busy = false);
  }

  Future<void> publish() async {
    final isDemo =
        widget.config['demo_mode'] == true || widget.job['is_demo'] == true;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          isDemo ? 'Имитировать публикацию?' : 'Опубликовать в Instagram?',
        ),
        content: Text(
          isDemo ? 'Это тест: настоящий Instagram не получит пост.' : 'Фотография и текст из этой карточки будут опубликованы в подключённом аккаунте.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Отмена'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Продолжить'),
          ),
        ],
      ),
    );
    if (accepted == true) await action('publish');
  }

  Widget section(String title, List<Widget> children) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 14),
          ...children,
        ],
      ),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final job = widget.job;
    final review = job['review'] as Map?;
    final post = job['post'] as Map?;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            job['title'],
            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text('${job['city']} · ${stageOf(job)}'),
          const SizedBox(height: 20),
          if (error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text(error!, style: const TextStyle(color: Colors.red)),
            ),
          section('Выполненная работа', [
            Text(job['description']),
            if (photo != null)
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.memory(
                    photo!,
                    height: 240,
                    width: double.infinity,
                    fit: BoxFit.contain,
                  ),
                ),
              ),
            const SizedBox(height: 12),
            Text(
              job['auto_publish'] == true
                  ? 'Автопубликация после разрешения клиента'
                  : 'Публикация после проверки мастером',
              style: const TextStyle(color: teal),
            ),
          ]),
          const SizedBox(height: 16),
          section('Отзыв клиента', [
            if (review == null) ...[
              const Text(
                'Создайте персональное приглашение и отправьте ссылку клиенту. Он сам начнёт диалог с ботом.',
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: busy ? null : () => action('invite'),
                icon: const Icon(Icons.link),
                label: const Text('Создать приглашение'),
              ),
            ] else ...[
              Text(statusNames[review['stage']] ?? review['stage']),
              if (link != null && link!.isNotEmpty) ...[
                const SizedBox(height: 12),
                SelectableText(link!),
                Wrap(
                  spacing: 8,
                  children: [
                    TextButton.icon(
                      onPressed: () =>
                          Clipboard.setData(ClipboardData(text: link!)),
                      icon: const Icon(Icons.copy),
                      label: const Text('Копировать'),
                    ),
                    TextButton(
                      onPressed: () => launchUrl(
                        Uri.parse(link!),
                        mode: LaunchMode.externalApplication,
                      ),
                      child: const Text('Открыть Telegram'),
                    ),
                  ],
                ),
              ],
              if (link == null && review['stage'] == 'INVITED') ...[
                const Padding(
                  padding: EdgeInsets.only(top: 12),
                  child: Text(
                    'Для нового приглашения создайте ссылку заново. Предыдущая перестанет действовать.',
                  ),
                ),
                OutlinedButton(
                  onPressed: busy ? null : () => action('invite'),
                  child: const Text('Создать новую ссылку'),
                ),
              ],
              if ((review['approved_text'] as String).isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: SelectableText('«${review['approved_text']}»'),
                ),
              const SizedBox(height: 12),
              Text(
                'Обработка AI: ${review['ai_consent'] ? 'разрешена' : 'не разрешена'}\nInstagram: ${review['public_consent'] ? 'разрешён' : 'не разрешён'}',
              ),
              if (widget.config['demo_mode'] == true &&
                  job['is_demo'] == true) ...[
                const Divider(height: 28),
                const Text(
                  'Симулятор клиента',
                  style: TextStyle(fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                if (chat == null)
                  OutlinedButton(
                    onPressed: busy ? null : () => action('demo-chat'),
                    child: const Text('Открыть тестовый диалог'),
                  )
                else ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: bg,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: SelectableText(chat!['text']),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: (chat!['choices'] as List)
                        .map<Widget>(
                          (c) => OutlinedButton(
                            onPressed: busy
                                ? null
                                : () => action('demo-chat', {'action': c[0]}),
                            child: Text(c[1]),
                          ),
                        )
                        .toList(),
                  ),
                  if (chat!['stage'] == 'CHATTING') ...[
                    const SizedBox(height: 12),
                    TextField(
                      controller: answer,
                      maxLength: 350,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Ответ клиента',
                      ),
                    ),
                    FilledButton(
                      onPressed: busy
                          ? null
                          : () => action('demo-chat', {'text': answer.text}),
                      child: const Text('Отправить ответ'),
                    ),
                  ],
                ],
              ],
            ],
          ]),
          const SizedBox(height: 16),
          section('Публикация', [
            if (post == null)
              Text(
                review?['public_consent'] == true
                    ? 'После получения разрешений AI подготовит пост. Можно запустить подготовку вручную.'
                    : 'Пост появится после подтверждения отзыва и разрешения публикации.',
              ),
            if (post == null && review?['public_consent'] == true)
              OutlinedButton(
                onPressed: busy ? null : () => action('generate'),
                child: const Text('Подготовить пост'),
              ),
            if (post != null) ...[
              Text(
                statusNames[post['status']] ?? post['status'],
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 12),
              if ((post['caption'] as String).isNotEmpty)
                SelectableText(post['caption']),
              if ((post['error'] as String).isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    post['error'],
                    style: const TextStyle(color: Colors.red),
                  ),
                ),
              const SizedBox(height: 16),
              if (post['status'] == 'DRAFT')
                FilledButton.icon(
                  onPressed: busy ? null : publish,
                  icon: const Icon(Icons.send_outlined),
                  label: Text(
                    (widget.config['demo_mode'] == true ||
                            job['is_demo'] == true)
                        ? 'Имитировать публикацию'
                        : 'Опубликовать в Instagram',
                  ),
                ),
              if (post['status'] == 'FAILED')
                OutlinedButton(
                  onPressed: busy ? null : () => action('retry'),
                  child: const Text('Повторить после проверки настроек'),
                ),
              if (post['status'] == 'DEMO')
                const Text(
                  'Сценарий пройден. В настоящий Instagram ничего не отправлено.',
                  style: TextStyle(color: teal),
                ),
              if ((post['permalink'] as String).isNotEmpty)
                TextButton(
                  onPressed: () => launchUrl(
                    Uri.parse(post['permalink']),
                    mode: LaunchMode.externalApplication,
                  ),
                  child: const Text('Открыть пост в Instagram'),
                ),
            ],
          ]),
        ],
      ),
    );
  }
}

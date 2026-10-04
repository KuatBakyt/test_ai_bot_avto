import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:review_studio/api.dart';
import 'package:review_studio/main.dart';

class FakeApi extends StudioApi {
  final bool authenticated;
  final List<Map<String, dynamic>> jobs;
  FakeApi({this.authenticated = false, this.jobs = const []});
  @override
  Future<bool> restore() async => authenticated;
  @override
  Future<dynamic> request(
    String path, {
    String method = 'GET',
    dynamic data,
    dynamic responseType,
  }) async {
    if (path == '/jobs/') return jobs;
    if (path == '/config/') {
      return {'demo_mode': true, 'instagram_enabled': false};
    }
    if (path.endsWith('/demo-chat/')) {
      return {
        'text': 'Можно обработать ответы с помощью AI?',
        'stage': 'CONSENT',
        'choices': [
          ['ai_yes', 'Разрешаю'],
        ],
      };
    }
    throw StateError(path);
  }
}

void main() {
  testWidgets('login asks for owner credentials', (tester) async {
    await tester.pumpWidget(StudioApp(api: FakeApi()));
    await tester.pumpAndSettle();
    expect(find.text('Review Studio'), findsOneWidget);
    expect(find.text('Логин'), findsOneWidget);
    expect(find.text('Пароль'), findsOneWidget);
    expect(find.text('Войти'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('demo and empty state stay clear on mobile', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(StudioApp(api: FakeApi(authenticated: true)));
    await tester.pumpAndSettle();
    expect(find.textContaining('Деморежим'), findsOneWidget);
    expect(find.text('Добавить'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('job details show client consent and demo simulator', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final job = <String, dynamic>{
      'id': 'job-1',
      'title': 'Ремонт смесителя',
      'description': 'Заменили картридж',
      'city': 'Алматы',
      'photo_present': false,
      'auto_publish': false,
      'is_demo': true,
      'review': {
        'stage': 'INVITED',
        'ai_consent': false,
        'public_consent': false,
        'approved_text': '',
      },
      'post': null,
    };
    await tester.pumpWidget(
      StudioApp(api: FakeApi(authenticated: true, jobs: [job])),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ремонт смесителя'));
    await tester.pumpAndSettle();
    expect(find.text('Симулятор клиента'), findsOneWidget);
    await tester.ensureVisible(find.text('Открыть тестовый диалог'));
    await tester.tap(find.text('Открыть тестовый диалог'));
    await tester.pumpAndSettle();
    expect(find.text('Можно обработать ответы с помощью AI?'), findsOneWidget);
    expect(find.text('Разрешаю'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
}

import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class StudioApi {
  final Dio dio;
  final FlutterSecureStorage storage;
  String? access;
  String? refresh;
  Future<void>? refreshing;
  StudioApi({Dio? client, FlutterSecureStorage? secureStorage})
    : dio =
          client ??
          Dio(
            BaseOptions(
              baseUrl: const String.fromEnvironment(
                'API_URL',
                defaultValue: 'http://localhost:8100/api/v1',
              ),
              connectTimeout: const Duration(seconds: 10),
              receiveTimeout: const Duration(seconds: 65),
            ),
          ),
      storage = secureStorage ?? const FlutterSecureStorage();
  Future<bool> restore() async {
    access = await storage.read(key: 'studio.access');
    refresh = await storage.read(key: 'studio.refresh');
    return access != null && refresh != null;
  }

  Future<void> login(String username, String password) async {
    final response = await dio.post(
      '/auth/login/',
      data: {'username': username, 'password': password},
    );
    await save(response.data);
  }

  Future<void> save(dynamic data) async {
    access = data['access'] as String;
    refresh = data['refresh'] as String? ?? refresh;
    await storage.write(key: 'studio.access', value: access);
    await storage.write(key: 'studio.refresh', value: refresh);
  }

  Future<void> logout() async {
    access = refresh = null;
    await storage.delete(key: 'studio.access');
    await storage.delete(key: 'studio.refresh');
  }

  Future<void> ensureToken() async {
    if (access == null) throw StateError('Войдите в аккаунт.');
    final body = jsonDecode(
      utf8.decode(base64Url.decode(base64Url.normalize(access!.split('.')[1]))),
    ) as Map;
    if ((body['exp'] as int) * 1000 >
        DateTime.now().millisecondsSinceEpoch + 60000) {
      return;
    }
    if (refreshing != null) return refreshing!;
    refreshing = () async {
      final result = await dio.post(
        '/auth/refresh/',
        data: {'refresh': refresh},
      );
      await save(result.data);
    }();
    try {
      await refreshing;
    } finally {
      refreshing = null;
    }
  }

  Future<dynamic> request(
    String path, {
    String method = 'GET',
    dynamic data,
    ResponseType? responseType,
  }) async {
    await ensureToken();
    final result = await dio.request(
      path,
      data: data,
      options: Options(
        method: method,
        responseType: responseType,
        headers: {'Authorization': 'Bearer $access'},
      ),
    );
    return result.data;
  }
}

String errorText(Object error) {
  if (error is DioException) {
    if (error.response?.statusCode == 401) {
      return 'Сессия истекла. Выйдите и войдите снова.';
    }
    final data = error.response?.data;
    if (data is Map) {
      return data.entries
          .map(
            (e) =>
                '${e.key == 'detail' || e.key == 'non_field_errors' ? '' : '${e.key}: '}${e.value is List ? (e.value as List).join(' ') : e.value}',
          )
          .join('\n');
    }
    return 'Сервер недоступен. Проверьте API_URL и запуск Docker.';
  }
  return 'Не удалось выполнить действие. Попробуйте снова.';
}

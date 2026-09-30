import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:record/record.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '감정 일기',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
      ),
      home: const LoginPage(),
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  String _message = '';

  Future<void> _login() async {
    final url = Uri.parse('https://emotiondiary-production-8c03.up.railway.app/login');
    final response = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': _emailController.text,
        'password': _passwordController.text,
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final token = data['access_token'];

      if (!mounted) return;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => RecordPage(token: token)),
      );
    } else {
      setState(() {
        _message = '로그인 실패: ${response.body}';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('로그인')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: _emailController,
              decoration: const InputDecoration(labelText: '이메일'),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _passwordController,
              decoration: const InputDecoration(labelText: '비밀번호'),
              obscureText: true,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _login,
              child: const Text('로그인'),
            ),
            const SizedBox(height: 16),
            Text(_message),
            const SizedBox(height: 24),
            TextButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => const SignupPage()),
                );
              },
              child: const Text('계정이 없으신가요? 회원가입'),
            ),
          ],
        ),
      ),
    );
  }
}

class RecordPage extends StatefulWidget {
  final String token;
  const RecordPage({super.key, required this.token});

  @override
  State<RecordPage> createState() => _RecordPageState();
}

class _RecordPageState extends State<RecordPage> {
  final _audioRecorder = AudioRecorder();
  bool _isRecording = false;
  String _message = '';

  Future<void> _startRecording() async {
    if (await _audioRecorder.hasPermission()) {
      await _audioRecorder.start(const RecordConfig(), path: 'temp_audio.m4a');
      setState(() {
        _isRecording = true;
        _message = '녹음 중...';
      });
    } else {
      setState(() {
        _message = '마이크 권한이 필요해요';
      });
    }
  }

  Future<void> _stopRecording() async {
  final path = await _audioRecorder.stop();
  setState(() {
    _isRecording = false;
    _message = '녹음 완료, 업로드 중...';
  });

  if (path != null) {
    final fileResponse = await http.get(Uri.parse(path));
    await _uploadBytes(fileResponse.bodyBytes);
  }
}

Future<void> _uploadBytes(List<int> bytes) async {
  final url = Uri.parse('https://emotiondiary-production-8c03.up.railway.app/transcrib');
  final request = http.MultipartRequest('POST', url);
  request.headers['Authorization'] = 'Bearer ${widget.token}';
  request.files.add(
    http.MultipartFile.fromBytes('file', bytes, filename: 'recording.m4a'),
  );

  final response = await request.send();
  final responseBody = await response.stream.bytesToString();

  if (response.statusCode == 200) {
    final data = jsonDecode(responseBody);
    setState(() {
      _message = '저장 완료: ${data['text']}';
    });
  } else {
    setState(() {
      _message = '업로드 실패: $responseBody';
    });
  }
}

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('음성 일기')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            IconButton(
              iconSize: 100,
              icon: Icon(_isRecording ? Icons.stop_circle : Icons.mic),
              color: _isRecording ? Colors.red : Colors.deepPurple,
              onPressed: _isRecording ? _stopRecording : _startRecording,
            ),
            const SizedBox(height: 24),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24),
              child: Text(_message, textAlign: TextAlign.center),
            ),
            const SizedBox(height: 40),
            TextButton(
              onPressed: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (context) => ResultPage(token: widget.token),
                  ),
                );
              },
              child: const Text('오늘 분석 결과 보기'),
            ),
          ],
        ),
      ),
    );
  }
}



  class ResultPage extends StatefulWidget {
  final String token;
  const ResultPage({super.key, required this.token});

  @override
  State<ResultPage> createState() => _ResultPageState();
}

class _ResultPageState extends State<ResultPage> {
  bool _loading = true;
  String _message = '';
  Map<String, dynamic>? _analysis;
  String? _youtubeLink;
  DateTime _selectedDate = DateTime.now();

  @override
  void initState() {
    super.initState();
    _fetchAnalysis();
  }

  Future<void> _fetchAnalysis() async {
    setState(() {
      _loading = true;
      _analysis = null;
    });

    final dateStr = _selectedDate.toIso8601String().substring(0, 10);
    final url = Uri.parse('https://emotiondiary-production-8c03.up.railway.app/analyze/$dateStr');

    final response = await http.post(
      url,
      headers: {'Authorization': 'Bearer ${widget.token}'},
    );

    final data = jsonDecode(response.body);

    setState(() {
      _loading = false;
      if (data['analysis'] != null) {
        _analysis = data['analysis'];
        _youtubeLink = data['youtube_link'];
      } else {
        _message = data['message'] ?? '결과를 가져오지 못했어요';
      }
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
    );

    if (picked != null) {
      setState(() {
        _selectedDate = picked;
      });
      _fetchAnalysis();
    }
  }

  @override
  Widget build(BuildContext context) {
    final dateStr = _selectedDate.toIso8601String().substring(0, 10);

    return Scaffold(
      appBar: AppBar(title: const Text('감정 분석 결과')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  dateStr,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                ElevatedButton.icon(
                  onPressed: _pickDate,
                  icon: const Icon(Icons.calendar_today),
                  label: const Text('날짜 선택'),
                ),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24.0),
                    child: _analysis == null
                        ? Center(child: Text(_message))
                        : SingleChildScrollView(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '오늘의 감정: ${_analysis!['dominant_emotion']}',
                                  style: const TextStyle(
                                      fontSize: 22, fontWeight: FontWeight.bold),
                                ),
                                const SizedBox(height: 16),
                                Text(_analysis!['summary']),
                                const SizedBox(height: 16),
                                Text(
                                  '조언: ${_analysis!['advice']}',
                                  style: const TextStyle(fontStyle: FontStyle.italic),
                                ),
                                const SizedBox(height: 24),
                                Text(
                                  '추천 노래: ${_analysis!['song_recommendation']}',
                                  style: const TextStyle(fontWeight: FontWeight.bold),
                                ),
                                const SizedBox(height: 8),
                                if (_youtubeLink != null)
                                  Text(
                                    _youtubeLink!,
                                    style: const TextStyle(color: Colors.blue),
                                  ),
                              ],
                            ),
                          ),
                  ),
          ),
        ],
      ),
    );
  }
}

class SignupPage extends StatefulWidget {
  const SignupPage({super.key});

  @override
  State<SignupPage> createState() => _SignupPageState();
}

class _SignupPageState extends State<SignupPage> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  String _message = '';

  Future<void> _signup() async {
    final url = Uri.parse('https://emotiondiary-production-8c03.up.railway.app/signup');
    final response = await http.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': _emailController.text,
        'password': _passwordController.text,
      }),
    );

    if (response.statusCode == 200) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('회원가입 완료! 로그인해주세요')),
      );
      Navigator.pop(context);
    } else {
      setState(() {
        _message = '회원가입 실패: ${response.body}';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('회원가입')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: _emailController,
              decoration: const InputDecoration(labelText: '이메일'),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _passwordController,
              decoration: const InputDecoration(labelText: '비밀번호'),
              obscureText: true,
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _signup,
              child: const Text('회원가입'),
            ),
            const SizedBox(height: 16),
            Text(_message),
          ],
        ),
      ),
    );
  }
}


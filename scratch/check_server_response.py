import urllib.request

with urllib.request.urlopen('http://localhost:8080/') as resp:
    data = resp.read().decode('utf-8')
    print('HTTP status:', resp.status)
    print('Has onclick toggleBenchmarkMode:', 'onclick="window.toggleBenchmarkMode()"' in data)
    print('Has window.toggleBenchmarkMode:', 'window.toggleBenchmarkMode = function()' in data)
    print('Has #btn-benchmark:', 'id="btn-benchmark"' in data)
    print('Has #main-mission-control:', 'id="main-mission-control"' in data)
    print('Has #benchmark-view:', 'id="benchmark-view"' in data)
    print('Has #btn-exit-benchmark:', 'id="btn-exit-benchmark"' in data)

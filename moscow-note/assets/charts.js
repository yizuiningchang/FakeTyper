// MoSCoW 工作量占比图
(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();

  var el = document.getElementById('chart-share');
  if (!el || typeof echarts === 'undefined') { return; }

  var tiers = [
    { name: 'Must have\n必须有', value: 60, alpha: 1 },
    { name: 'Should have\n应该有', value: 20, alpha: 0.62 },
    { name: 'Could have\n可以有', value: 20, alpha: 0.62 },
    { name: "Won't have\n本期不做", value: 0, alpha: 0.34 }
  ];

  var chart = echarts.init(el, null, { renderer: 'svg' });

  chart.setOption({
    animation: false,
    grid: { left: 104, right: 88, top: 16, bottom: 28 },
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      formatter: function (p) {
        return p.name.replace('\n', ' · ') + '：' +
          (p.value === 0 ? '不占工作量' : '约 ' + p.value + '% 的工作量');
      }
    },
    xAxis: {
      type: 'value',
      max: 70,
      axisLabel: { formatter: '{value}%', color: muted, fontSize: 12 },
      splitLine: { lineStyle: { color: rule } },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: tiers.map(function (t) { return t.name; }),
      axisLabel: { color: ink, fontSize: 12, lineHeight: 16 },
      axisLine: { lineStyle: { color: rule } },
      axisTick: { show: false }
    },
    series: [{
      type: 'bar',
      barWidth: 22,
      data: tiers.map(function (t) { return t.value; }),
      itemStyle: {
        borderRadius: [0, 4, 4, 0],
        color: function (p) { return accent + Math.round(tiers[p.dataIndex].alpha * 255).toString(16).padStart(2, '0'); }
      },
      label: {
        show: true,
        position: 'right',
        color: ink,
        fontSize: 12,
        formatter: function (p) { return p.value === 0 ? '不占工作量' : '约 ' + p.value + '%'; }
      }
    }]
  });

  window.addEventListener('resize', function () { chart.resize(); });
})();

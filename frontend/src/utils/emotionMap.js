export const emotionMap = {
  neutral: { label: '普通', face: '^_^', tone: '屏幕里的常驻嘉宾待机中', color: '#5b6ee1' },
  happy: { label: '开心', face: '^-^', tone: 'LunaClaw 上线，状态不错', color: '#f2a541' },
  sad: { label: '安慰', face: '-_-', tone: '陪伴模式，语气放轻', color: '#6e8ef2' },
  thinking: { label: '思考', face: 'o_o', tone: '正在把问题拆成小块', color: '#7a6ff0' },
  surprised: { label: '惊讶', face: 'O_O', tone: '这波有点东西', color: '#e36b8c' },
  serious: { label: '认真', face: '._.', tone: '认真处理，不玩虚的', color: '#45515f' }
}

export function getEmotionMeta(emotion) {
  return emotionMap[emotion] || emotionMap.neutral
}

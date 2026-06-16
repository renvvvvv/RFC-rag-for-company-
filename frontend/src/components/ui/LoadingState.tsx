import { Spin, Space, Typography } from 'antd'
import { colors, spacing, typography } from '@/styles/theme'

const { Text } = Typography

interface LoadingStateProps {
  tip?: string
  fullHeight?: boolean
}

const LoadingState: React.FC<LoadingStateProps> = ({ tip = '加载中...', fullHeight = false }) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing.xxl,
        height: fullHeight ? 'calc(100vh - 200px)' : 'auto',
      }}
    >
      <Space direction="vertical" align="center" size={spacing.md}>
        <Spin size="large" style={{ color: colors.accent }} />
        <Text style={{ color: colors.textMuted, fontSize: typography.sizes.sm }}>{tip}</Text>
      </Space>
    </div>
  )
}

export default LoadingState

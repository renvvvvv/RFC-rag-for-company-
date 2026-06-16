import { Result, Button } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { colors, spacing } from '@/styles/theme'

interface ErrorStateProps {
  title?: string
  subTitle?: string
  onRetry?: () => void
}

const ErrorState: React.FC<ErrorStateProps> = ({
  title = '加载失败',
  subTitle = '请检查网络连接或稍后重试',
  onRetry,
}) => {
  return (
    <div style={{ padding: spacing.xxl }}>
      <Result
        status="error"
        title={title}
        subTitle={subTitle}
        extra={
          onRetry && (
            <Button type="primary" icon={<ReloadOutlined />} onClick={onRetry} style={{ background: colors.accent, borderColor: colors.accent }}>
              重新加载
            </Button>
          )
        }
      />
    </div>
  )
}

export default ErrorState

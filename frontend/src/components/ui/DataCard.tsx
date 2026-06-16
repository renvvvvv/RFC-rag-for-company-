import { Card } from 'antd'
import { colors, radius, shadows, spacing } from '@/styles/theme'

interface DataCardProps {
  title?: React.ReactNode
  extra?: React.ReactNode
  children: React.ReactNode
  style?: React.CSSProperties
  bodyStyle?: React.CSSProperties
  hoverable?: boolean
}

const DataCard: React.FC<DataCardProps> = ({
  title,
  extra,
  children,
  style,
  bodyStyle,
  hoverable = false,
}) => {
  return (
    <Card
      title={title}
      extra={extra}
      hoverable={hoverable}
      style={{
        borderRadius: radius.lg,
        border: `1px solid ${colors.border}`,
        boxShadow: shadows.sm,
        background: colors.surface,
        ...style,
      }}
      bodyStyle={{ padding: spacing.lg, ...bodyStyle }}
    >
      {children}
    </Card>
  )
}

export default DataCard

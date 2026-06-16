import { Space, Typography } from 'antd'
import { colors, typography, spacing } from '@/styles/theme'

const { Title, Text } = Typography

interface PageHeaderProps {
  title: string
  subtitle?: string
  children?: React.ReactNode
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, subtitle, children }) => {
  return (
    <div style={{ marginBottom: spacing.xl }}>
      <Space direction="vertical" size={spacing.sm} style={{ width: '100%' }}>
        <Title
          level={3}
          style={{
            margin: 0,
            color: colors.textPrimary,
            fontSize: typography.sizes['2xl'],
            fontWeight: typography.weights.semibold,
            letterSpacing: '-0.02em',
          }}
        >
          {title}
        </Title>
        {subtitle && (
          <Text style={{ color: colors.textMuted, fontSize: typography.sizes.md, lineHeight: typography.lineHeights.relaxed }}>
            {subtitle}
          </Text>
        )}
      </Space>
      {children && <div style={{ marginTop: spacing.md }}>{children}</div>}
    </div>
  )
}

export default PageHeader

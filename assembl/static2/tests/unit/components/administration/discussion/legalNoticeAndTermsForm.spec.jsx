import React from 'react';
import ShallowRenderer from 'react-test-renderer/shallow';

import { LegalNoticeAndTermsForm } from '../../../../../js/app/components/administration/discussion/legalNoticeAndTermsForm';

describe('LegalNoticeAndTermsForm component', () => {
  it('should render a form to edit legal notice and terms and conditions', () => {
    const updateLegalNoticeSpy = jest.fn(() => {});
    const updateTermsAndConditionsSpy = jest.fn(() => {});
    const props = {
      locale: 'en',
      legalNotice: '',
      termsAndConditions: '',
      updateLegalNotice: updateLegalNoticeSpy,
      updateTermsAndConditions: updateTermsAndConditionsSpy
    };
    const shallowRenderer = new ShallowRenderer();
    shallowRenderer.render(<LegalNoticeAndTermsForm {...props} />);
    const result = shallowRenderer.getRenderOutput();
    expect(result).toMatchSnapshot();
  });
});